from typing import final

from ghostcompanion.core.entity.portfolio import Portfolio
from ghostcompanion.core.entity.trade import Trade
from ghostcompanion.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter


@final
class ExportPortfolio:
    def __init__(self, ghostfolio: GhostfolioAdapter) -> None:
        self.ghostfolio = ghostfolio

    def execute(self, portfolio: Portfolio) -> None:
        print(f"Started exporting {portfolio.account.name} activities to Ghostfolio...")
        for symbol in portfolio.get_symbols():
            orders = self.ghostfolio.get_orders_by_symbol(portfolio.account.id, symbol)

            if portfolio.account.name == "Interactive Brokers":
                # At the moment, IBKR trades are being imported from FlexQueries.
                # These files have trades from at most 365 days old.
                # When deleting outdated orders, we shouldn't delete orders older than that,
                # because we won't add them again based on the importer.
                orders = self._filter_ghostfolio_orders_older_than_oldest_asset_trade(
                    portfolio, symbol, orders
                )

            outdated_orders = portfolio.get_absent_trades(symbol, orders)
            if outdated_orders:
                print(f"Deleting outdated orders for `{symbol}`...")
                self.ghostfolio.delete_orders(outdated_orders)
                orders = [order for order in orders if order not in outdated_orders]

            if orders:
                portfolio.delete_repeated_trades(symbol, orders)

        print("Exporting new activities to Ghostfolio...")
        self.ghostfolio.export_portfolio(portfolio)

    @staticmethod
    def _filter_ghostfolio_orders_older_than_oldest_asset_trade(
        portfolio: Portfolio, symbol: str, orders: list[Trade]
    ) -> list[Trade]:
        oldest_trade = portfolio.get_oldest_trade(symbol)
        return list(
            filter(
                lambda x: x.executed_at.date() >= oldest_trade.executed_at.date(),
                orders,
            )
        )
