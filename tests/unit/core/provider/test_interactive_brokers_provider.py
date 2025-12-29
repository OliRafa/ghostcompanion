from pytest import fixture

from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.provider.interactive_brokers import InteractiveBrokersProvider
from tests.infra.interactive_brokers_api import InMemoryInteractiveBrokersApi
from tests.resources.interactive_brokers import CANCEL_TRADES


class TastytradeAdapterFactory:
    @fixture(autouse=True, scope="function")
    def initialize_interactive_brokers_provider(self):
        self.interactive_brokers_provider: InteractiveBrokersProvider = (
            InteractiveBrokersProvider(InMemoryInteractiveBrokersApi())
        )


class TestGetDividends(TastytradeAdapterFactory):
    def when_given_synbol_should_return_dividends_for_symbol(self):
        dividends = self.interactive_brokers_provider.get_dividends("STOCKA")

        assert dividends

    def should_not_return_dividend_reverts(self):
        dividends = self.interactive_brokers_provider.get_dividends("STOCKA")

        assert len(dividends) == 1

    def should_have_timezone_in_executed_at(self):
        dividends = self.interactive_brokers_provider.get_dividends("STOCKA")

        dividend = dividends[0]

        assert dividend.executed_at.tzinfo


class TestGetSymbols(TastytradeAdapterFactory):
    def should_return_all_symbols(self):
        results = self.interactive_brokers_provider.get_symbols()

        assert sorted(results) == ["STOCKA", "STOCKB"]


class TestGetTrades(TastytradeAdapterFactory):
    def when_given_asset_should_return_trades_for_requested_asset_only(self):
        results = self.interactive_brokers_provider.get_trades("STOCKA")

        assert len(results) >= 1
        assert all(trade.symbol == "STOCKA" for trade in results)

    def should_return_only_buy_sell_trades(self):
        trades = self.interactive_brokers_provider.get_trades("STOCKB")

        assert all(
            trade.transaction_type == TransactionType.BUY
            or trade.transaction_type == TransactionType.SELL
            for trade in trades
        )

    def when_theres_cancel_trade_followed_by_completed_trade_should_return_correct_trade(
        self,
    ):
        self.interactive_brokers_provider.interactive_brokers_api = (
            InMemoryInteractiveBrokersApi(CANCEL_TRADES)
        )
        trades = self.interactive_brokers_provider.get_trades("STOCKC")

        assert len(trades) == 1

        trade = trades[0]

        assert trade.transaction_type == TransactionType.BUY
        assert trade.fee > 0

    def when_trade_is_sell_should_return_positive_quantity(self):
        trades = self.interactive_brokers_provider.get_trades("STOCKA")

        trade = trades[0]

        assert trade.quantity > 0

    def should_have_fee_as_positive_value(self):
        trades = self.interactive_brokers_provider.get_trades("STOCKA")

        trade = trades[0]

        assert trade.fee > 0

    def should_have_timezone_in_executed_at(self):
        trades = self.interactive_brokers_provider.get_trades("STOCKA")

        trade = trades[0]

        assert trade.executed_at.tzinfo
