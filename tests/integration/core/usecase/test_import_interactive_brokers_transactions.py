from pytest import fixture

from ghostcompanion.core.entity.symbol_change import SymbolChange
from ghostcompanion.core.provider.interactive_brokers import InteractiveBrokersProvider
from ghostcompanion.core.usecase.import_interactive_brokers_transactions import (
    ImportInteractiveBrokersTransactions,
)
from ghostcompanion.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from tests.infra.ghostfolio_api import InMemoryGhostfolioApi
from tests.infra.interactive_brokers_api import InMemoryInteractiveBrokersApi
from tests.infra.symbol_mapping_repository import InMemorySymbolMappingRepository


class ImportInteractiveBrokersTransactionsFactory:
    @fixture(autouse=True)
    def initialize_import_interactive_brokers_transactions(self):
        self.import_interactive_brokers_transactions: ImportInteractiveBrokersTransactions = ImportInteractiveBrokersTransactions(
            InteractiveBrokersProvider(InMemoryInteractiveBrokersApi()),
            GhostfolioAdapter(InMemoryGhostfolioApi()),
            InMemorySymbolMappingRepository(),
        )


class TestImportInteractiveBrokersTransactions(
    ImportInteractiveBrokersTransactionsFactory
):
    def should_add_assets_to_portfolio(self):
        portfolio = self.import_interactive_brokers_transactions.execute()

        assert portfolio.get_symbols()

    def should_use_yahoo_as_data_source(self):
        portfolio = self.import_interactive_brokers_transactions.execute()

        trades = portfolio.get_trades("STOCKA")

        assert all(trade.data_source == "YAHOO" for trade in trades)

    def should_take_into_account_symbol_maps(self):
        symbol_mapping_repository = InMemorySymbolMappingRepository(
            [SymbolChange(old_symbol="STOCKA", new_symbol="NEWSTOCKA")]
        )
        self.import_interactive_brokers_transactions.symbol_mapping_repository = (
            symbol_mapping_repository
        )

        portfolio = self.import_interactive_brokers_transactions.execute()

        assert portfolio.has_asset("NEWSTOCKA") is True

    def when_theres_forex_trade_should_not_include_it_in_assets(self):
        portfolio = self.import_interactive_brokers_transactions.execute()

        assert portfolio.has_asset("FOREX") is False
