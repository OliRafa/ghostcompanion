import logging

from ghostcompanion.core.entity.portfolio import Portfolio
from ghostcompanion.core.provider.tastytrade import TastytradeProvider
from ghostcompanion.infra.dividends_provider.dividends_provider_adapter import (
    DividendsProviderAdapter,
)
from ghostcompanion.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from ghostcompanion.repositories.config import ConfigRepository

logger = logging.getLogger(__name__)


class ImportTastytradeTransactions:
    def __init__(
        self,
        dividends_provider: DividendsProviderAdapter,
        ghostfolio: GhostfolioAdapter,
        config_repository: ConfigRepository,
        tastytrade: TastytradeProvider,
    ) -> None:
        self.dividends_provider = dividends_provider
        self.ghostfolio = ghostfolio
        self.config_repository = config_repository
        self.tastytrade = tastytrade

    def execute(self) -> Portfolio:
        ghostfolio_account = self.ghostfolio.get_or_create_account("Tastytrade")
        portfolio = Portfolio(ghostfolio_account)

        logger.info("Started getting all Tastytrade transactions")
        symbol_changes = self.tastytrade.get_symbol_changes()
        if symbol_changes:
            logger.info("Adapting symbol changes")
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
                    logger.info(
                        f'Deleting outdated orders for "{change.old_symbol}" '
                        f'after changing to "{change.new_symbol}"'
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
            logger.info("Handling stock splits")
            portfolio.adapt_stock_splits(stock_splits)

        symbol_mappings = self.config_repository.get_symbol_mappings()
        if symbol_mappings:
            logger.info("Handling symbol changes from config file")
            portfolio.adapt_symbol_changes(symbol_mappings)

        return portfolio
