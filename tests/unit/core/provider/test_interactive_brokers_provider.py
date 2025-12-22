from pytest import fixture

from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.provider.interactive_brokers import InteractiveBrokersProvider
from tests.infra.interactive_brokers_api import InMemoryInteractiveBrokersApi


class TastytradeAdapterFactory:
    @fixture(autouse=True, scope="function")
    def initialize_interactive_brokers_provider(self):
        self.interactive_brokers_provider: InteractiveBrokersProvider = (
            InteractiveBrokersProvider(InMemoryInteractiveBrokersApi())
        )


class TestGetAssets(TastytradeAdapterFactory):
    def should_return_all_assets(self):
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

    def when_trade_is_sell_should_return_positive_quantity(self):
        trades = self.interactive_brokers_provider.get_trades("STOCKA")

        trade = trades[0]

        assert trade.quantity > 0

    def should_have_fee_as_positive_value(self):
        trades = self.interactive_brokers_provider.get_trades("STOCKA")

        trade = trades[0]

        assert trade.fee > 0
