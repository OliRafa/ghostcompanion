"""End-to-end: import Tastytrade transactions into a real Ghostfolio instance
and read the persisted activities back to prove the transforms (splits,
dividends) land correctly."""

from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.provider.tastytrade import TastytradeProvider
from ghostcompanion.core.usecase.export_portfolio import ExportPortfolio
from ghostcompanion.core.usecase.import_tastytrade_transactions import (
    ImportTastytradeTransactions,
)
from ghostcompanion.infra.dividends_provider.dividends_provider_adapter import (
    DividendsProviderAdapter,
)
from tests.e2e.resources.stubs import InMemoryTastytradeApi, StubYahooFinanceApi
from tests.infra.symbol_mapping_repository import InMemorySymbolMappingRepository


class TastytradeTransactionsE2E:
    @fixture(autouse=True)
    def imported_portfolio(self, ghostfolio):
        self.ghostfolio = ghostfolio
        provider = TastytradeProvider(InMemoryTastytradeApi())
        dividends = DividendsProviderAdapter(StubYahooFinanceApi())
        use_case = ImportTastytradeTransactions(
            dividends, ghostfolio, InMemorySymbolMappingRepository(), provider
        )

        self.portfolio = use_case.execute()
        ExportPortfolio(ghostfolio).execute(self.portfolio)

    def orders_for(self, symbol: str):
        return self.ghostfolio.get_orders_by_symbol(self.portfolio.account.id, symbol)


class TestReverseSplit(TastytradeTransactionsE2E):
    def should_persist_reverse_split_adjusted_position(self):
        orders = self.orders_for("AAPL")

        buys = [
            order for order in orders if order.transaction_type == TransactionType.BUY
        ]
        assert len(buys) == 1
        # 8 shares @ 100, 1-for-4 reverse split -> 2 shares @ 400.
        assert buys[0].quantity == Decimal("2")
        assert buys[0].unit_price == Decimal("400")


class TestForwardSplit(TastytradeTransactionsE2E):
    def should_persist_forward_split_adjusted_position(self):
        orders = self.orders_for("MSFT")

        buys = [
            order for order in orders if order.transaction_type == TransactionType.BUY
        ]
        assert len(buys) == 1
        # 5 shares @ 100, 2-for-1 forward split -> 10 shares @ 50.
        assert buys[0].quantity == Decimal("10")
        assert buys[0].unit_price == Decimal("50")


class TestDividend(TastytradeTransactionsE2E):
    def should_persist_received_dividend(self):
        orders = self.orders_for("KO")

        dividends = [
            order
            for order in orders
            if order.transaction_type == TransactionType.DIVIDEND
        ]
        assert len(dividends) == 1
        # $25 dividend enriched at $0.50/share -> 50 shares.
        assert dividends[0].quantity == Decimal("50")
        assert dividends[0].unit_price == Decimal("0.5")


class TestSymbolChange(TastytradeTransactionsE2E):
    def should_persist_position_under_new_symbol(self):
        new_orders = self.orders_for("META")
        old_orders = self.orders_for("FB")

        assert len(old_orders) == 0
        buys = [
            order
            for order in new_orders
            if order.transaction_type == TransactionType.BUY
        ]
        # 3 FB shares @ 100 renamed to META, unchanged.
        assert len(buys) == 1
        assert buys[0].quantity == Decimal("3")
        assert buys[0].unit_price == Decimal("100")


class TestImportedSymbols(TastytradeTransactionsE2E):
    def should_persist_every_expected_symbol(self):
        for symbol in ("AAPL", "MSFT", "KO", "META"):
            assert self.orders_for(symbol), f"{symbol} was not persisted"

        # FB was renamed to META, so nothing should remain under it.
        assert not self.orders_for("FB")
