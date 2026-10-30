import logging
from datetime import datetime, timezone
from decimal import Decimal

from pytest import fixture, raises

from ghostcompanion.core.entity.wallet import Network
from ghostcompanion.core.exceptions import PriceNotFoundException
from ghostcompanion.infra.market_prices.market_price_adapter import MarketPriceAdapter
from tests.infra.defillama_api import InMemoryDefiLlamaApi
from tests.infra.yahoo_finance_api import InMemoryYahooFinanceApi

CBBTC = "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf"


def at(day: str) -> datetime:
    return datetime.fromisoformat(day).replace(tzinfo=timezone.utc)


class MarketPriceAdapterFactory:
    @fixture(autouse=True)
    def initialize_adapter(self):
        self.yahoo_finance_api = InMemoryYahooFinanceApi()
        self.defillama_api = InMemoryDefiLlamaApi()
        self.market_prices = MarketPriceAdapter(self.yahoo_finance_api)
        self.moment_prices = MarketPriceAdapter(
            self.yahoo_finance_api, self.defillama_api
        )


class TestDailyClose(MarketPriceAdapterFactory):
    def should_return_close_on_given_day(self):
        price = self.market_prices.get_crypto_price(
            "BTC", "USD", at("2024-03-01T15:00:00"), Network.BITCOIN
        )

        assert price == Decimal("61000.0")

    def when_day_has_no_close_should_return_latest_close_before_it(self):
        price = self.market_prices.get_crypto_price(
            "BTC", "USD", at("2024-05-31T00:00:00"), Network.BITCOIN
        )

        assert price == Decimal("61000.0")

    def when_day_is_after_last_close_should_return_last_close(self):
        price = self.market_prices.get_crypto_price(
            "BTC", "USD", at("2030-01-01T00:00:00"), Network.BITCOIN
        )

        assert price == Decimal("65000.0")

    def when_day_is_before_first_close_should_raise_exception(self):
        with raises(PriceNotFoundException):
            self.market_prices.get_crypto_price(
                "BTC", "USD", at("2019-12-31T00:00:00"), Network.BITCOIN
            )

    def when_ticker_is_unknown_should_raise_exception(self):
        with raises(PriceNotFoundException):
            self.market_prices.get_crypto_price(
                "NOPE", "USD", at("2024-01-01T00:00:00"), Network.BITCOIN
            )

    def should_fetch_history_once_per_ticker(self):
        calls = []
        get_price_history = self.yahoo_finance_api.get_price_history
        self.yahoo_finance_api.get_price_history = lambda ticker: (
            calls.append(ticker) or get_price_history(ticker)
        )

        for month in (1, 3, 6):
            self.market_prices.get_crypto_price(
                "BTC", "USD", at(f"2024-0{month}-01T00:00:00"), Network.BITCOIN
            )

        assert calls == ["BTC-USD"]


class TestMomentPrice(MarketPriceAdapterFactory):
    def should_return_defillama_price_at_the_moment(self):
        price = self.moment_prices.get_crypto_price(
            "BTC", "USD", at("2026-09-17T08:41:12"), Network.BASE, CBBTC
        )

        assert price == Decimal("76318.55")

    def should_name_tokens_by_network_and_contract(self):
        self.moment_prices.get_crypto_price(
            "BTC", "USD", at("2026-09-17T08:41:12"), Network.BASE, CBBTC
        )

        assert self.defillama_api.requests == [
            (f"base:{CBBTC}", at("2026-09-17T08:41:12"))
        ]

    def should_name_a_network_coin_by_the_zero_address(self):
        price = self.moment_prices.get_crypto_price(
            "ETH", "USD", at("2024-01-05T18:45:00"), Network.ETHEREUM
        )

        assert price == Decimal("2247.18")

    def should_name_bitcoin_by_its_coingecko_id(self):
        price = self.moment_prices.get_crypto_price(
            "BTC", "USD", at("2021-07-14T09:27:52"), Network.BITCOIN
        )

        assert price == Decimal("32740.15")

    def should_ask_defillama_once_per_coin_and_moment(self):
        for _ in range(2):
            self.moment_prices.get_crypto_price(
                "BTC", "USD", at("2026-09-17T08:41:12"), Network.BASE, CBBTC
            )

        assert len(self.defillama_api.requests) == 1

    def when_coin_has_no_network_should_return_daily_close(self):
        price = self.moment_prices.get_crypto_price(
            "XLM", "USD", at("2021-06-03T10:15:00"), None
        )

        assert price == Decimal("0.3861")
        assert self.defillama_api.requests == []

    def when_currency_is_not_usd_should_not_ask_defillama(self):
        with raises(PriceNotFoundException, match="BTC-EUR"):
            self.moment_prices.get_crypto_price(
                "BTC", "EUR", at("2024-03-01T12:00:00"), Network.BITCOIN
            )

        assert self.defillama_api.requests == []


class TestFallback(MarketPriceAdapterFactory):
    def when_defillama_has_no_price_should_return_daily_close(self, caplog):
        with caplog.at_level(logging.WARNING):
            price = self.moment_prices.get_crypto_price(
                "BTC", "USD", at("2024-06-02T12:00:00"), Network.BITCOIN
            )

        assert price == Decimal("67000.0")
        assert "DefiLlama has no price for `coingecko:bitcoin`" in caplog.text
        assert "Yahoo's `BTC-USD` close of 2024-06-02" in caplog.text

    def when_defillama_fails_should_stop_asking_it(self, caplog):
        self.defillama_api.unreachable = True

        with caplog.at_level(logging.WARNING):
            prices = [
                self.moment_prices.get_crypto_price(
                    "BTC", "USD", at(moment), Network.BITCOIN
                )
                for moment in ("2024-03-01T12:00:00", "2024-06-02T12:00:00")
            ]

        assert prices == [Decimal("61000.0"), Decimal("67000.0")]
        assert len(self.defillama_api.requests) == 1
        assert caplog.text.count("DefiLlama failed") == 1
