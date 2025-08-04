from decimal import Decimal
from typing import Any

from tastytrade_ghostfolio.core.entity.account import GhostfolioAccount
from tastytrade_ghostfolio.core.entity.portfolio import Portfolio
from tastytrade_ghostfolio.core.entity.trade import Trade
from tastytrade_ghostfolio.core.entity.transaction_type import TransactionType
from tastytrade_ghostfolio.infra.ghostfolio.ghostfolio_api import GhostfolioApi


class GhostfolioAdapter:
    def __init__(self, ghostfolio_api: GhostfolioApi):
        self.ghostfolio_api = ghostfolio_api
        self._orders: list[dict[str, Any]] = []

    def get_or_create_account(
        self, name: str, currency: str | None = None
    ) -> GhostfolioAccount:
        accounts = self.ghostfolio_api.get_accounts()

        try:
            account = next(
                filter(lambda x: x["name"].lower() == name.lower(), accounts)
            )
            return GhostfolioAccount(**account)

        except StopIteration:
            print(f"Creating new `{name}` account in Ghostfolio...")
            account_data = {
                "balance": 0.0,
                "comment": "Managed by Tastytrade-Ghostfolio.",
                "currency": currency if currency else "USD",
                "name": name,
                "platformId": None,
            }

            created_account = self.ghostfolio_api.create_account(account_data)
            account = GhostfolioAccount.model_construct(**created_account)

            return account

    def adapt_crypto_symbol(self, symbol: str) -> str:
        return f"{symbol}USD"

    def _get_orders(self, account_id: str) -> list[Trade]:
        orders = self.ghostfolio_api.get_orders(account_id)
        return [self._adapt_order(order) for order in orders]

    def get_orders_by_symbol(self, account_id: str, symbol: str) -> list[Trade]:
        self._orders = self._get_orders(account_id)
        return [order for order in self._orders if order.symbol == symbol]

    @staticmethod
    def _adapt_order(order: dict[str, Any]) -> Trade:
        return Trade(
            currency=order["currency"],
            description=order["comment"],
            executed_at=order["date"],
            fee=Decimal(str(order["fee"])),
            id=order["id"],
            quantity=Decimal(str(order["quantity"])),
            symbol=order["SymbolProfile"]["symbol"],
            transaction_type=TransactionType(order["type"]),
            unit_price=Decimal(str(order["unitPrice"])),
        )

    def delete_orders(self, orders: list[Trade]):
        for order in orders:
            self.ghostfolio_api.delete_order_by_id(order.id)

    def export_portfolio(self, portfolio: Portfolio):
        orders = []
        for asset in portfolio.get_symbols():
            trades = portfolio.get_trades(asset)
            dividends = portfolio.get_dividends(asset)
            orders += [
                self._adapt_trade(portfolio.account.id, trade)
                for trade in trades + dividends
            ]

        self.ghostfolio_api.insert_orders(orders)

    @staticmethod
    def _adapt_trade(account_id: str, trade: Trade) -> dict[str, str | float]:
        return {
            "accountId": account_id,
            "comment": trade.description,
            "currency": trade.currency,
            "dataSource": trade.data_source,
            "date": str(trade.executed_at),
            "fee": float(trade.fee),
            "quantity": float(trade.quantity),
            "symbol": trade.symbol,
            "type": trade.transaction_type.value,
            "unitPrice": float(trade.unit_price),
        }
