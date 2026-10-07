import datetime
from bisect import bisect_right
from decimal import Decimal
from typing import final

from ghostcompanion.core.exceptions import PriceNotFoundException
from ghostcompanion.core.ports.market_prices import MarketPricePort
from ghostcompanion.infra.dividends_provider.yahoo_finance_api import YahooFinanceApi


@final
class MarketPriceAdapter(MarketPricePort):
    def __init__(self, yahoo_finance_api: YahooFinanceApi):
        self.yahoo_finance_api = yahoo_finance_api
        self._closes: dict[str, tuple[list[datetime.date], list[Decimal]]] = {}

    def get_crypto_price(
        self, symbol: str, currency: str, day: datetime.date
    ) -> Decimal:
        return self._close_on(f"{symbol}-{currency}", day)

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
