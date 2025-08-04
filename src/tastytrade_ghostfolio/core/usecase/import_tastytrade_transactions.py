from tastytrade_ghostfolio.core.entity.portfolio import Portfolio
from tastytrade_ghostfolio.infra.dividends_provider.dividends_provider_adapter import (
    DividendsProviderAdapter,
)
from tastytrade_ghostfolio.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from tastytrade_ghostfolio.infra.tastytrade.tastytrade_adapter import TastytradeAdapter
from tastytrade_ghostfolio.repositories.symbol_mapping import (
    SymbolMappingRepository,
    SymbolMappingsNotFoundException,
)


class ImportTastytradeTransactions:
    def __init__(
        self,
        dividends_provider: DividendsProviderAdapter,
        ghostfolio: GhostfolioAdapter,
        symbol_mapping_repository: SymbolMappingRepository,
        tastytrade: TastytradeAdapter,
    ) -> None:
        self.dividends_provider = dividends_provider
        self.ghostfolio = ghostfolio
        self.symbol_mapping_repository = symbol_mapping_repository
        self.tastytrade = tastytrade

    def execute(self) -> Portfolio:
        ghostfolio_account = self.ghostfolio.get_or_create_account("Tastytrade")
        portfolio = Portfolio(ghostfolio_account)

        print("Started getting all Tastytrade transactions...")
        symbol_changes = self.tastytrade.get_symbol_changes()
        if symbol_changes:
            print("Adapting symbol changes...")
            for change in symbol_changes:
                trades = self.tastytrade.get_trades(change.old_symbol)
                portfolio.add_asset(change.old_symbol, trades)

                trades = self.tastytrade.get_trades(change.new_symbol)
                portfolio.add_asset(change.new_symbol, trades)
                portfolio.adapt_symbol_changes(symbol_changes)

                old_dividends = self.tastytrade.get_dividends(change.old_symbol)
                new_dividends = self.tastytrade.get_dividends(change.new_symbol)
                if old_dividends or new_dividends:
                    dividend_infos = self.dividends_provider.get_by_symbol(
                        change.new_symbol
                    )
                    if old_dividends:
                        for dividend in old_dividends:
                            dividend.symbol = change.new_symbol

                    portfolio.add_dividends(
                        change.new_symbol, old_dividends + new_dividends, dividend_infos
                    )

                outdated_orders = self.ghostfolio.get_orders_by_symbol(
                    portfolio.account.id, change.old_symbol
                )
                if outdated_orders:
                    print(
                        f'Deleting outdated orders for "{change.old_symbol}" '
                        f'after changing to "{change.new}"...'
                    )
                    self.ghostfolio.delete_orders(outdated_orders)

        symbols = self.tastytrade.get_assets()
        symbols = [
            symbol
            for symbol in symbols
            if symbol not in portfolio.get_symbols() and symbol not in symbol_changes
        ]
        for symbol in symbols:
            trades = self.tastytrade.get_trades(symbol)
            portfolio.add_asset(symbol, trades)

            dividends = self.tastytrade.get_dividends(symbol)
            if dividends:
                dividend_infos = self.dividends_provider.get_by_symbol(symbol)
                portfolio.add_dividends(symbol, dividends, dividend_infos)

        stock_splits = self.tastytrade.get_splits()
        if stock_splits:
            print("Handling stock splits...")
            portfolio.adapt_stock_splits(stock_splits)

        try:
            symbol_mappings = self.symbol_mapping_repository.get_symbol_mappings()
            print("Handling symbol changes from mapping file...")
            portfolio.adapt_symbol_changes(symbol_mappings)

        except SymbolMappingsNotFoundException:
            print("Skipping symbol changes from mapping file, as no file was found.")

        return portfolio
