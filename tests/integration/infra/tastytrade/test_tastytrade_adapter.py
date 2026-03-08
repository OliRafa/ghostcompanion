from pytest import fixture

from ghostcompanion.infra.tastytrade.tastytrade_adapter import TastytradeAdapter
from tests.infra.tastytrade_api import InMemoryTastytradeApi


class TastytradeAdapterFactory:
    @fixture(autouse=True, scope="function")
    def tastytrade_adapter(self) -> None:
        self.tastytrade_adapter = TastytradeAdapter(InMemoryTastytradeApi())


class TestGetTradesHistory(TastytradeAdapterFactory):
    def should_return_trades_history(self):
        results = self.tastytrade_adapter.get_trades_history()

        assert len(results) > 0
        assert all(hasattr(tx, "transaction_type") for tx in results)
