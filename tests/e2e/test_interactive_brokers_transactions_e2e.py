"""End-to-end: import Interactive Brokers transactions into a real Ghostfolio
instance and read the persisted activities back to prove the trades (buys, sells,
dividends) land correctly."""

from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.provider.interactive_brokers import InteractiveBrokersProvider
from ghostcompanion.core.usecase.export_portfolio import ExportPortfolio
from ghostcompanion.core.usecase.import_interactive_brokers_transactions import (
    ImportInteractiveBrokersTransactions,
)
from tests.e2e.resources.interactive_brokers import InMemoryInteractiveBrokersApi
from tests.infra.symbol_mapping_repository import InMemorySymbolMappingRepository


class InteractiveBrokersTransactionsE2E:
    @fixture(autouse=True)
    def imported_portfolio(self, ghostfolio):
        self.ghostfolio = ghostfolio
        provider = InteractiveBrokersProvider(InMemoryInteractiveBrokersApi())
        use_case = ImportInteractiveBrokersTransactions(
            provider, ghostfolio, InMemorySymbolMappingRepository()
        )

        self.portfolio = use_case.execute()
        ExportPortfolio(ghostfolio).execute(self.portfolio)

    def orders_for(self, symbol: str):
        return self.ghostfolio.get_orders_by_symbol(self.portfolio.account.id, symbol)


class TestBuy(InteractiveBrokersTransactionsE2E):
    def should_persist_bought_position(self):
        orders = self.orders_for("AAPL")

        buys = [o for o in orders if o.transaction_type == TransactionType.BUY]
        assert len(buys) == 1
        assert buys[0].quantity == Decimal("10")
        assert buys[0].unit_price == Decimal("150")


class TestSell(InteractiveBrokersTransactionsE2E):
    def should_persist_bought_and_sold_positions(self):
        orders = self.orders_for("NVDA")

        buys = [o for o in orders if o.transaction_type == TransactionType.BUY]
        sells = [o for o in orders if o.transaction_type == TransactionType.SELL]
        assert len(buys) == 1
        assert buys[0].quantity == Decimal("8")
        assert buys[0].unit_price == Decimal("120")
        assert len(sells) == 1
        # IBKR sells carry a negative quantity; the provider stores the absolute.
        assert sells[0].quantity == Decimal("3")
        assert sells[0].unit_price == Decimal("130")


class TestDividend(InteractiveBrokersTransactionsE2E):
    def should_persist_received_dividend(self):
        orders = self.orders_for("AAPL")

        dividends = [
            o for o in orders if o.transaction_type == TransactionType.DIVIDEND
        ]
        assert len(dividends) == 1
        assert dividends[0].quantity == Decimal("10")
        assert dividends[0].unit_price == Decimal("0.25")


class TestImportedSymbols(InteractiveBrokersTransactionsE2E):
    def should_persist_every_expected_symbol(self):
        for symbol in ("AAPL", "MSFT", "NVDA"):
            assert self.orders_for(symbol), f"{symbol} was not persisted"
