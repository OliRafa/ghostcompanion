import datetime
import logging
from bisect import bisect_right
from decimal import Decimal
from typing import final

from ghostcompanion.core.entity.wallet import Network
from ghostcompanion.core.exceptions import PriceNotFoundException
from ghostcompanion.core.ports.market_prices import MarketPricePort
from ghostcompanion.infra.defillama.defillama_api import (
    DefiLlamaApi,
    DefiLlamaException,
)
from ghostcompanion.infra.dividends_provider.yahoo_finance_api import YahooFinanceApi

logger = logging.getLogger(__name__)

# DefiLlama names a chain's own coin by the zero address, and Bitcoin, which has
# no contracts, by its CoinGecko id.
_NATIVE_CONTRACT = "0x" + "0" * 40
_BITCOIN = "coingecko:bitcoin"
_DEFILLAMA_CURRENCY = "USD"


@final
class MarketPriceAdapter(MarketPricePort):
    """Prices a coin at the moment asked through DefiLlama, or, without
    DefiLlama or a price from it, at Yahoo's daily close."""

    def __init__(
        self,
        yahoo_finance_api: YahooFinanceApi,
        defillama_api: DefiLlamaApi | None = None,
    ):
        self.yahoo_finance_api = yahoo_finance_api
        self.defillama_api = defillama_api
        self._defillama_failed = False
        self._closes: dict[str, tuple[list[datetime.date], list[Decimal]]] = {}
        self._moment_prices: dict[tuple[str, datetime.datetime], Decimal | None] = {}

    def get_crypto_price(
        self,
        symbol: str,
        currency: str,
        moment: datetime.datetime,
        network: Network | None,
        contract: str | None = None,
    ) -> Decimal:
        ticker = f"{symbol}-{currency}"
        if network is not None and self._asks_defillama(currency):
            coin = self._defillama_coin(network, contract)
            try:
                price = self._price_at(coin, moment)
            except DefiLlamaException as error:
                # Asking again for every other movement would only wait out the
                # same failure each time.
                self._defillama_failed = True
                logger.warning(
                    f"DefiLlama failed ({error}); the remaining prices are Yahoo's"
                    " daily closes"
                )
            else:
                if price is not None:
                    return price
                logger.warning(
                    f"DefiLlama has no price for `{coin}` at {moment.isoformat()};"
                    f" using Yahoo's `{ticker}` close of {moment.date()}"
                )

        return self._close_on(ticker, moment.date())

    def _asks_defillama(self, currency: str) -> bool:
        return (
            self.defillama_api is not None
            and not self._defillama_failed
            and currency == _DEFILLAMA_CURRENCY
        )

    @staticmethod
    def _defillama_coin(network: Network, contract: str | None) -> str:
        if network is Network.BITCOIN:
            return _BITCOIN
        return f"{network.value}:{contract or _NATIVE_CONTRACT}"

    def _price_at(self, coin: str, moment: datetime.datetime) -> Decimal | None:
        key = (coin, moment)
        if key not in self._moment_prices:
            self._moment_prices[key] = self.defillama_api.get_price(coin, moment)

        return self._moment_prices[key]

    def _close_on(self, ticker: str, day: datetime.date) -> Decimal:
        days, closes = self._get_closes(ticker)

        # A day without a close yet (a transaction made today) takes the latest
        # close before it.
        position = bisect_right(days, day)
        if position == 0:
            raise PriceNotFoundException(f"No `{ticker}` close on or before {day}")

        return closes[position - 1]

    def _get_closes(self, ticker: str) -> tuple[list[datetime.date], list[Decimal]]:
        if ticker not in self._closes:
            history = self.yahoo_finance_api.get_price_history(ticker).dropna()
            self._closes[ticker] = (
                [timestamp.date() for timestamp in history.index],
                [Decimal(str(close)) for close in history.values],
            )

        return self._closes[ticker]
