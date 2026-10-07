import datetime
from decimal import Decimal

from pytest import fixture, raises

from ghostcompanion.core.exceptions import PriceNotFoundException
from ghostcompanion.infra.market_prices.market_price_adapter import MarketPriceAdapter
from tests.infra.yahoo_finance_api import InMemoryYahooFinanceApi


class MarketPriceAdapterFactory:
    @fixture(autouse=True)
    def initialize_adapter(self):
        self.yahoo_finance_api = InMemoryYahooFinanceApi()
        self.market_prices = MarketPriceAdapter(self.yahoo_finance_api)


class TestGetCryptoPrice(MarketPriceAdapterFactory):
    def should_return_close_on_given_day(self):
        price = self.market_prices.get_crypto_price(
            "BTC", "USD", datetime.date(2024, 3, 1)
        )

        assert price == Decimal("61000.0")

    def when_day_has_no_close_should_return_latest_close_before_it(self):
        price = self.market_prices.get_crypto_price(
            "BTC", "USD", datetime.date(2024, 5, 31)
        )

        assert price == Decimal("61000.0")

    def when_day_is_after_last_close_should_return_last_close(self):
        price = self.market_prices.get_crypto_price(
            "BTC", "USD", datetime.date(2030, 1, 1)
        )

        assert price == Decimal("67000.0")

    def when_day_is_before_first_close_should_raise_exception(self):
        with raises(PriceNotFoundException):
            self.market_prices.get_crypto_price(
                "BTC", "USD", datetime.date(2019, 12, 31)
            )

    def when_ticker_is_unknown_should_raise_exception(self):
        with raises(PriceNotFoundException):
            self.market_prices.get_crypto_price(
                "NOPE", "USD", datetime.date(2024, 1, 1)
            )

    def should_fetch_history_once_per_ticker(self):
        calls = []
        get_price_history = self.yahoo_finance_api.get_price_history
        self.yahoo_finance_api.get_price_history = lambda ticker: (
            calls.append(ticker) or get_price_history(ticker)
        )

        for month in (1, 3, 6):
            self.market_prices.get_crypto_price(
                "BTC", "USD", datetime.date(2024, month, 1)
            )

        assert calls == ["BTC-USD"]
