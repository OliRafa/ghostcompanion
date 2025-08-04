from ghostcompanion.core.entity.portfolio import Portfolio
from ghostcompanion.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter


class ExportPortfolio:
    def __init__(self, ghostfolio: GhostfolioAdapter) -> None:
        self.ghostfolio = ghostfolio

    def execute(self, portfolio: Portfolio) -> None:
        print(f"Started exporting {portfolio.account.name} activities to Ghostfolio...")
        for symbol in portfolio.get_symbols():
            orders = self.ghostfolio.get_orders_by_symbol(portfolio.account.id, symbol)

            outdated_orders = portfolio.get_absent_trades(symbol, orders)
            if outdated_orders:
                print(f"Deleting outdated orders for `{symbol}`...")
                self.ghostfolio.delete_orders(outdated_orders)
                orders = [order for order in orders if order not in outdated_orders]

            if orders:
                portfolio.delete_repeated_trades(symbol, orders)

        print("Exporting new activities to Ghostfolio...")
        self.ghostfolio.export_portfolio(portfolio)
