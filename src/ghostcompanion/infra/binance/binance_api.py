import logging
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from binance_common.configuration import ConfigurationRestAPI
from binance_common.errors import TooManyRequestsError
from binance_common.models import ApiResponse
from binance_sdk_fiat.fiat import Fiat
from binance_sdk_spot.spot import Spot
from binance_sdk_wallet.wallet import Wallet

from ghostcompanion.configs.settings import BinanceSettings
from ghostcompanion.core.ports.binance import BinancePort

logger = logging.getLogger(__name__)

# Binance opened on this day: no history can be older.
_LAUNCH = datetime(2017, 7, 14, tzinfo=timezone.utc)
# Deposit and withdrawal history is only returned 90 days at a time.
_HISTORY_WINDOW = timedelta(days=89)
_HISTORY_PAGE_LIMIT = 1000
_FIAT_PAGE_ROWS = 500
_TRADES_PAGE_LIMIT = 1000
# Spot calls may weigh 6000 a minute; pausing short of it leaves room for the
# next call, which weighs 20 at most.
_WEIGHT_PAUSE_AT = 5800
_TIMEOUT_MILLISECONDS = 30_000
_RATE_LIMIT_RETRIES = 3


class BinanceApi(BinancePort):
    def __init__(self) -> None:
        configuration = ConfigurationRestAPI(
            api_key=BinanceSettings.API_KEY,
            api_secret=BinanceSettings.SECRET,
            timeout=_TIMEOUT_MILLISECONDS,
        )
        self._spot = Spot(config_rest_api=configuration).rest_api
        self._wallet = Wallet(config_rest_api=configuration).rest_api
        self._fiat = Fiat(config_rest_api=configuration).rest_api

    def get_balances(self) -> dict[str, Decimal]:
        balances: dict[str, Decimal] = defaultdict(Decimal)
        account = self._call(self._spot.get_account, omit_zero_balances=True)
        for balance in account["balances"]:
            balances[balance["asset"]] += Decimal(balance["free"]) + Decimal(
                balance["locked"]
            )
        for balance in self._call(self._wallet.funding_wallet):
            balances[balance["asset"]] += sum(
                Decimal(balance[key])
                for key in ("free", "locked", "freeze", "withdrawing")
            )

        return {asset: amount for asset, amount in balances.items() if amount != 0}

    def get_deposits(self) -> list[dict[str, Any]]:
        return self._read_history(self._wallet.deposit_history)

    def get_withdrawals(self) -> list[dict[str, Any]]:
        return self._read_history(self._wallet.withdraw_history)

    def get_fiat_deposits(self) -> list[dict[str, Any]]:
        return self._read_fiat_orders("0")

    def get_fiat_withdrawals(self) -> list[dict[str, Any]]:
        return self._read_fiat_orders("1")

    def get_symbols(self) -> list[dict[str, Any]]:
        return self._call(self._spot.exchange_info)["symbols"]

    def get_trades(self, symbol: str) -> list[dict[str, Any]]:
        trades: list[dict[str, Any]] = []
        while True:
            page = self._call(
                self._spot.my_trades,
                symbol=symbol,
                from_id=trades[-1]["id"] + 1 if trades else 0,
                limit=_TRADES_PAGE_LIMIT,
            )
            trades += page
            if len(page) < _TRADES_PAGE_LIMIT:
                return trades

    def _read_history(
        self, endpoint: Callable[..., ApiResponse]
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        start = _LAUNCH
        now = datetime.now(timezone.utc)
        while start < now:
            end = min(start + _HISTORY_WINDOW, now)
            offset = 0
            while True:
                page = self._call(
                    endpoint,
                    start_time=_milliseconds(start),
                    end_time=_milliseconds(end),
                    offset=offset,
                    limit=_HISTORY_PAGE_LIMIT,
                )
                records += page
                if len(page) < _HISTORY_PAGE_LIMIT:
                    break
                offset += len(page)
            start = end + timedelta(milliseconds=1)

        return records

    def _read_fiat_orders(self, transaction_type: str) -> list[dict[str, Any]]:
        orders: list[dict[str, Any]] = []
        page = 1
        while True:
            response = self._call(
                self._fiat.get_fiat_deposit_withdraw_history,
                transaction_type=transaction_type,
                begin_time=_milliseconds(_LAUNCH),
                end_time=_milliseconds(datetime.now(timezone.utc)),
                page=page,
                rows=_FIAT_PAGE_ROWS,
            )
            rows = response.get("data") or []
            orders += rows
            if len(rows) < _FIAT_PAGE_ROWS:
                return orders
            page += 1

    def _call(self, endpoint: Callable[..., ApiResponse], **params: Any) -> Any:
        for attempt in range(_RATE_LIMIT_RETRIES + 1):
            try:
                response = endpoint(**params)
                break
            except TooManyRequestsError:
                if attempt == _RATE_LIMIT_RETRIES:
                    raise
                logger.warning("Binance rate limit reached; waiting a minute")
                time.sleep(60)

        self._pace(response)
        return _as_records(response.data())

    @staticmethod
    def _pace(response: ApiResponse):
        for limit in response.rate_limits:
            if (
                limit.rateLimitType == "REQUEST_WEIGHT"
                and limit.interval == "MINUTE"
                and limit.count >= _WEIGHT_PAUSE_AT
            ):
                # The weight is counted per minute of the clock.
                time.sleep(61 - datetime.now(timezone.utc).second)


def _as_records(data: Any) -> Any:
    """The SDK's models as the API's own records, without the SDK's extras."""
    if isinstance(data, list):
        return [_as_records(x) for x in data]
    if hasattr(data, "to_dict"):
        return _as_records(data.to_dict())
    if isinstance(data, dict):
        return {
            key: _as_records(value)
            for key, value in data.items()
            if key != "additional_properties"
        }
    return data


def _milliseconds(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)
