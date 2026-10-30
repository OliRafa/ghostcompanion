import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from functools import cached_property
from typing import Any

from ghostcompanion.core.entity.binance import BinanceRecord
from ghostcompanion.core.entity.cash_balance import CashBalance
from ghostcompanion.core.entity.onchain_movement import OnChainMovement
from ghostcompanion.core.entity.trade import Trade
from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.entity.wallet import Network
from ghostcompanion.core.exceptions import PriceNotFoundException
from ghostcompanion.core.ports.binance import BinancePort
from ghostcompanion.core.ports.market_prices import MarketPricePort
from ghostcompanion.core.provider.binance_history import (
    FIAT,
    BinanceExchange,
    BinanceHistory,
    exchanges_of_trades,
    read_history,
)

logger = logging.getLogger(__name__)

_CURRENCY = "USD"
# DefiLlama prices these at the moment; any other coin only has a daily close.
_NETWORK_COINS = {"BTC": Network.BITCOIN, "ETH": Network.ETHEREUM}

_DEPOSIT_DONE = {1, 6}  # credited, withdrawable or not yet
_WITHDRAWAL_DONE = 6
_FIAT_ORDER_DONE = "Successful"
_API_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

_TRADING_FEE_DESCRIPTION = "Trading fee"
_AIRDROP_DESCRIPTION = "Airdrop"


class BinanceProvider:
    """Binance's trades, airdrops and transfers.

    Binance's API no longer returns trades from before September 2022, so they
    come from the Transaction Records exports. The API has every deposit and
    withdrawal, with transaction ids that pair them with the user's other
    accounts, and the trades since the exports end. Those are looked for only
    when the balances say there were some, as scanning pairs takes minutes.
    """

    ACCOUNT_NAME = "Binance"

    def __init__(
        self,
        binance_api: BinancePort,
        market_prices: MarketPricePort,
        records: list[BinanceRecord] | None = None,
    ):
        self.binance_api = binance_api
        self.market_prices = market_prices
        self.records = sorted(records or [], key=lambda x: x.executed_at)

    def get_trades(self) -> list[Trade]:
        """Trades against fiat, the fees of every trade, and airdrops."""
        trades = [self._adapt_gift(x) for x in self._history.gifts]
        for exchange in self._exchanges:
            trade = self._adapt_fiat_trade(exchange)
            if trade:
                trades.append(trade)
            trades += self._adapt_fees(exchange)

        return trades

    def get_movements(self) -> list[OnChainMovement]:
        """Deposits and withdrawals, which may be transfers between the user's
        accounts, and trades of a coin for another, which are swaps."""
        movements = [self._adapt_deposit(x) for x in self._deposits]
        movements += [self._adapt_withdrawal(x) for x in self._withdrawals]
        for exchange in self._exchanges:
            if exchange.given not in FIAT and exchange.got not in FIAT:
                movements += self._adapt_swap(exchange)

        return movements

    def get_current_cash_balance(self, currency: str) -> CashBalance:
        return CashBalance(
            date=date.today(),
            amount=self._balances.get(currency, Decimal("0")),
            currency=currency,
        )

    @cached_property
    def _history(self) -> BinanceHistory:
        history = read_history(self.records)
        for operation, count in history.unread.items():
            logger.warning(
                f"`{self.ACCOUNT_NAME}`: {count} `{operation}` record(s) in the"
                " exports aren't booked, so its holdings will be off by them"
            )

        return history

    @cached_property
    def _exchanges(self) -> list[BinanceExchange]:
        self._check_transfers()
        return self._history.exchanges + self._exchanges_since_records()

    @cached_property
    def _deposits(self) -> list[dict[str, Any]]:
        return [
            x for x in self.binance_api.get_deposits() if x["status"] in _DEPOSIT_DONE
        ]

    @cached_property
    def _withdrawals(self) -> list[dict[str, Any]]:
        return [
            x
            for x in self.binance_api.get_withdrawals()
            if x["status"] == _WITHDRAWAL_DONE
        ]

    @cached_property
    def _balances(self) -> dict[str, Decimal]:
        return {
            self._rename(coin): amount
            for coin, amount in self.binance_api.get_balances().items()
        }

    @property
    def _records_end(self) -> datetime | None:
        return self.records[-1].executed_at if self.records else None

    def _exchanges_since_records(self) -> list[BinanceExchange]:
        """The trades the API has from after the exports end. Only a coin whose
        balance its records don't explain can have been traded, and so can the
        coins traded for it."""
        expected = self._balances_after_transfers()
        changed = _differences(expected, self._balances)
        if not changed:
            return []

        logger.info(
            f"`{self.ACCOUNT_NAME}` balances of {', '.join(changed)} changed since"
            " its exports: looking for its trades, which can take minutes"
        )
        exchanges = self._find_exchanges(set(changed))
        for exchange in exchanges:
            expected[exchange.got] += exchange.got_quantity
            expected[exchange.given] -= exchange.given_quantity
            for coin, fee in exchange.fees.items():
                expected[coin] -= fee

        for coin, (held, booked) in _differences(expected, self._balances).items():
            logger.warning(
                f"`{self.ACCOUNT_NAME}` holds {held} {coin}, but its records add up"
                f" to {booked}: something the importer doesn't read (Earn, Convert,"
                " dust conversions…) moved it, and the difference isn't booked"
            )

        return exchanges

    def _balances_after_transfers(self) -> defaultdict[str, Decimal]:
        """The balances the exports end with, plus what the API says was
        deposited and withdrawn since."""
        end = self._records_end
        balances: defaultdict[str, Decimal] = defaultdict(Decimal)
        for record in self.records:
            balances[self._rename(record.coin)] += record.change

        for coin, change in self._transfers(lambda moment: _after(moment, end)):
            balances[coin] += change
        # A fiat withdrawal's amount is what reached the bank, its fee aside.
        orders = [(x, 1, "amount") for x in self.binance_api.get_fiat_deposits()]
        orders += [
            (x, -1, "indicatedAmount") for x in self.binance_api.get_fiat_withdrawals()
        ]
        for order, sign, field in orders:
            created_at = _from_milliseconds(order["createTime"])
            if order["status"] == _FIAT_ORDER_DONE and _after(created_at, end):
                balances[order["fiatCurrency"]] += sign * Decimal(order[field])

        return balances

    def _transfers(self, when: Callable[[datetime], bool]) -> list[tuple[str, Decimal]]:
        """How each deposit and withdrawal made `when` changed its coin's
        balance, a withdrawal's fee included."""
        changes = [
            (self._rename(x["coin"]), Decimal(x["amount"]))
            for x in self._deposits
            if when(_from_milliseconds(x["insertTime"]))
        ]
        changes += [
            (
                self._rename(x["coin"]),
                -Decimal(x["amount"]) - Decimal(x["transactionFee"]),
            )
            for x in self._withdrawals
            if when(_withdrawn_at(x))
        ]
        return changes

    def _find_exchanges(self, coins: set[str]) -> list[BinanceExchange]:
        symbols = self.binance_api.get_symbols()
        pending, scanned_coins, scanned_symbols = set(coins), set(), set()
        exchanges: list[BinanceExchange] = []
        while pending:
            coin = pending.pop()
            scanned_coins.add(coin)
            for symbol in symbols:
                pair = (symbol["baseAsset"], symbol["quoteAsset"])
                if coin not in pair or symbol["symbol"] in scanned_symbols:
                    continue
                scanned_symbols.add(symbol["symbol"])
                trades = [
                    x
                    for x in self.binance_api.get_trades(symbol["symbol"])
                    if _after(_from_milliseconds(x["time"]), self._records_end)
                ]
                if trades:
                    exchanges += exchanges_of_trades(symbol, trades)
                    pending |= set(pair) - scanned_coins

        return sorted(exchanges, key=lambda x: x.executed_at)

    def _check_transfers(self):
        """The exports' deposits and withdrawals should be the API's, since
        those are what's booked."""
        end = self._records_end
        if end is None:
            return

        recorded: defaultdict[str, Decimal] = defaultdict(Decimal)
        for record in self._history.transfers:
            recorded[record.coin] += record.change
        listed: defaultdict[str, Decimal] = defaultdict(Decimal)
        for coin, change in self._transfers(lambda moment: not _after(moment, end)):
            listed[coin] += change

        for coin, (api, exports) in _differences(recorded, listed).items():
            logger.warning(
                f"`{self.ACCOUNT_NAME}` deposits and withdrawals of {coin} up to"
                f" {end:%Y-%m-%d} add up to {api} in the API but {exports} in the"
                " exports: the API's are booked, so holdings will be off by the"
                " difference"
            )

    @staticmethod
    def _adapt_fiat_trade(exchange: BinanceExchange) -> Trade | None:
        if exchange.given in FIAT and exchange.got in FIAT:
            return None
        if exchange.given in FIAT:
            return Trade(
                currency=exchange.given,
                executed_at=exchange.executed_at,
                fee=exchange.fees.get(exchange.given, Decimal("0")),
                quantity=exchange.got_quantity,
                symbol=exchange.got,
                transaction_type=TransactionType.BUY,
                value=exchange.given_quantity,
            )
        if exchange.got in FIAT:
            return Trade(
                currency=exchange.got,
                executed_at=exchange.executed_at,
                fee=exchange.fees.get(exchange.got, Decimal("0")),
                quantity=exchange.given_quantity,
                symbol=exchange.given,
                transaction_type=TransactionType.SELL,
                value=exchange.got_quantity,
            )
        return None

    @staticmethod
    def _adapt_fees(exchange: BinanceExchange) -> list[Trade]:
        # A fee in a coin is that coin sold for nothing, as network fees are.
        # It's dated a second later because Ghostfolio orders activities of the
        # same second at random, and selling a fee out of the coin just bought
        # before the buy lands would take the holding below zero.
        return [
            Trade(
                description=_TRADING_FEE_DESCRIPTION,
                executed_at=exchange.executed_at + timedelta(seconds=1),
                fee=Decimal("0"),
                quantity=fee,
                symbol=coin,
                transaction_type=TransactionType.SELL,
                unit_price=Decimal("0"),
            )
            for coin, fee in exchange.fees.items()
            if coin not in FIAT and fee > 0
        ]

    def _adapt_swap(self, exchange: BinanceExchange) -> list[OnChainMovement]:
        # The ledger values a swap by whichever side has a price, so only the
        # best priced side gets one: a coin DefiLlama prices at the moment over
        # a daily close.
        prices: dict[str, Decimal | None] = {exchange.given: None, exchange.got: None}
        for coin in sorted(prices, key=lambda x: x not in _NETWORK_COINS):
            prices[coin] = self._price(coin, exchange.executed_at)
            if prices[coin] is not None:
                break

        return [
            OnChainMovement(
                account=self.ACCOUNT_NAME,
                currency=_CURRENCY,
                executed_at=exchange.executed_at,
                market_unit_price=prices[coin],
                quantity=quantity,
                symbol=coin,
                transaction_id=exchange.reference,
            )
            for coin, quantity in (
                (exchange.given, -exchange.given_quantity),
                (exchange.got, exchange.got_quantity),
            )
        ]

    def _adapt_deposit(self, deposit: dict[str, Any]) -> OnChainMovement:
        symbol = self._rename(deposit["coin"])
        executed_at = _from_milliseconds(deposit["insertTime"])
        return OnChainMovement(
            account=self.ACCOUNT_NAME,
            currency=_CURRENCY,
            executed_at=executed_at,
            market_unit_price=self._price(symbol, executed_at),
            quantity=Decimal(deposit["amount"]),
            symbol=symbol,
            transaction_id=deposit.get("txId") or None,
        )

    def _adapt_withdrawal(self, withdrawal: dict[str, Any]) -> OnChainMovement:
        symbol = self._rename(withdrawal["coin"])
        executed_at = _withdrawn_at(withdrawal)
        return OnChainMovement(
            account=self.ACCOUNT_NAME,
            currency=_CURRENCY,
            destination_address=withdrawal.get("address") or None,
            executed_at=executed_at,
            fee=Decimal(withdrawal["transactionFee"]),
            market_unit_price=self._price(symbol, executed_at),
            quantity=-Decimal(withdrawal["amount"]),
            symbol=symbol,
            transaction_id=withdrawal.get("txId") or None,
        )

    @staticmethod
    def _adapt_gift(record: BinanceRecord) -> Trade:
        return Trade(
            description=_AIRDROP_DESCRIPTION,
            executed_at=record.executed_at,
            fee=Decimal("0"),
            quantity=record.change,
            symbol=record.coin,
            transaction_type=TransactionType.BUY,
            unit_price=Decimal("0"),
        )

    def _price(self, coin: str, moment: datetime) -> Decimal | None:
        try:
            return self.market_prices.get_crypto_price(
                coin, _CURRENCY, moment, _NETWORK_COINS.get(coin)
            )
        except PriceNotFoundException:
            return None

    def _rename(self, coin: str) -> str:
        return self._history.renames.get(coin, coin)


def _differences(
    expected: dict[str, Decimal], actual: dict[str, Decimal]
) -> dict[str, tuple[Decimal, Decimal]]:
    """Each coin whose amounts differ, with what `actual` and `expected` have."""
    return {
        coin: (actual.get(coin, Decimal("0")), expected.get(coin, Decimal("0")))
        for coin in sorted(set(expected) | set(actual))
        if actual.get(coin, Decimal("0")) != expected.get(coin, Decimal("0"))
    }


def _after(moment: datetime, end: datetime | None) -> bool:
    return end is None or moment > end


def _withdrawn_at(withdrawal: dict[str, Any]) -> datetime:
    # The exports date a withdrawal when it completed; it's applied for earlier.
    moment = withdrawal.get("completeTime") or withdrawal["applyTime"]
    return datetime.strptime(moment, _API_TIME_FORMAT).replace(tzinfo=timezone.utc)


def _from_milliseconds(milliseconds: int) -> datetime:
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)
