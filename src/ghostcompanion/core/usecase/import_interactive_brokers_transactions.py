from typing import final

from ghostcompanion.core.entity.portfolio import Portfolio
from ghostcompanion.core.provider.interactive_brokers import InteractiveBrokersProvider
from ghostcompanion.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from ghostcompanion.repositories.symbol_mapping import (
    SymbolMappingRepository,
    SymbolMappingsNotFoundException,
)


@final
class ImportInteractiveBrokersTransactions:
    def __init__(
        self,
        interactive_brokers_provider: InteractiveBrokersProvider,
        ghostfolio: GhostfolioAdapter,
        symbol_mapping_repository: SymbolMappingRepository,
    ) -> None:
        self.interactive_brokers_provider = interactive_brokers_provider
        self.ghostfolio = ghostfolio
        self.symbol_mapping_repository = symbol_mapping_repository

    def execute(self) -> Portfolio:
        ghostfolio_account = self.ghostfolio.get_or_create_account(
            "Interactive Brokers"
        )
        portfolio = Portfolio(ghostfolio_account)

        print("Started getting all Interactive Brokers transactions...")
        symbols = self.interactive_brokers_provider.get_symbols()
        for symbol in symbols:
            trades = self.interactive_brokers_provider.get_trades(symbol)
            portfolio.add_asset(symbol, trades)

            dividends = self.interactive_brokers_provider.get_dividends(symbol)
            if dividends:
                portfolio.add_dividends(symbol, dividends)

        try:
            symbol_mappings = self.symbol_mapping_repository.get_symbol_mappings()
            print("Handling symbol changes from mapping file...")
            portfolio.adapt_symbol_changes(symbol_mappings)

        except SymbolMappingsNotFoundException:
            print("Skipping symbol changes from mapping file, as no file was found.")

        return portfolio
