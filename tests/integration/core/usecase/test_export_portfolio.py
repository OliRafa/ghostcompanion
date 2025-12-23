from datetime import timedelta

from pytest import fixture

from ghostcompanion.core.provider.interactive_brokers import InteractiveBrokersProvider
from ghostcompanion.core.usecase.export_portfolio import ExportPortfolio
from ghostcompanion.core.usecase.import_interactive_brokers_transactions import (
    ImportInteractiveBrokersTransactions,
)
from ghostcompanion.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from tests.infra.ghostfolio_api import InMemoryGhostfolioApi
from tests.infra.interactive_brokers_api import InMemoryInteractiveBrokersApi
from tests.infra.symbol_mapping_repository import InMemorySymbolMappingRepository


class ExportPortfolioFactory:
    @fixture(autouse=True)
    def initialize_export_portfolio(self):
        self.ghostfolio_adapter: GhostfolioAdapter = GhostfolioAdapter(
            InMemoryGhostfolioApi()
        )
        self.import_interactive_brokers_transactions: ImportInteractiveBrokersTransactions = ImportInteractiveBrokersTransactions(
            InteractiveBrokersProvider(InMemoryInteractiveBrokersApi()),
            self.ghostfolio_adapter,
            InMemorySymbolMappingRepository(),
        )
        self.export_portfolio: ExportPortfolio = ExportPortfolio(
            self.ghostfolio_adapter
        )


class TestExportPortfolio(ExportPortfolioFactory):
    def when_deleting_outdated_orders_from_ibkr_should_not_delete_older_than_oldest_trade(
        self,
    ):
        """At the moment, IBKR trades are being imported from FlexQueries.
        These files have trades from at most 365 days old.
        When deleting outdated trades, we shouldn't delete trades older than that,
        because we won't add them again based on the importer.
        """
        legacy_portfolio = self.import_interactive_brokers_transactions.execute()
        trades = legacy_portfolio.get_trades("STOCKA")
        for trade in trades:
            trade.executed_at - timedelta(days=365)

        self.ghostfolio_adapter.export_portfolio(legacy_portfolio)

        portfolio = self.import_interactive_brokers_transactions.execute()
        self.export_portfolio.execute(portfolio)

        orders = self.ghostfolio_adapter.get_orders_by_symbol(
            portfolio.account.id, "STOCKA"
        )
        assert len(orders) == 2
