from datetime import date, datetime
from decimal import Decimal
from typing import Any, final

from ghostcompanion.core.entity.account import GhostfolioAccount
from ghostcompanion.core.entity.cash_balance import CashBalance
from ghostcompanion.core.entity.portfolio import Portfolio
from ghostcompanion.core.entity.trade import Trade
from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.ports.ghostfolio import GhostfolioPort


@final
class GhostfolioAdapter:
    def __init__(self, ghostfolio_api: GhostfolioPort):
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
                "comment": "Managed by Ghostcompanion.",
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

    # Cash Balance Methods

    def create_account_balance(
        self, account_id: str, date: date, value: Decimal
    ) -> dict:
        """Create a new cash balance entry.

        Parameters
        ----------
        account_id : str
            The account ID.
        date : date
            The balance date.
        value : Decimal
            The cash balance value.

        Returns
        -------
        dict
            The created balance object.
        """
        return self.ghostfolio_api.create_account_balance(account_id, date, value)

    def get_latest_account_balance(self, account_id: str) -> CashBalance | None:
        """Get the most recent cash balance for an account.

        Parameters
        ----------
        account_id : str
            The Ghostfolio account ID.

        Returns
        -------
        CashBalance | None
            The latest CashBalance, or None if no balances exist.
        """
        ghostfolio_data = self.ghostfolio_api.get_account_balances(account_id)

        if not ghostfolio_data:
            return None

        # Sort by date and get the most recent
        latest = max(ghostfolio_data, key=lambda b: b["date"])

        # Parse date string - handle both formats:
        # - Real API: '2026-03-17T00:00:00.000Z' (with timestamp)
        # - InMemory: '2026-03-18' (date only)
        date_str = latest["date"]
        try:
            # Try full ISO format with timestamp first
            parsed_datetime = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            parsed_date = parsed_datetime.date()
        except ValueError:
            # Fall back to simple date format
            parsed_date = date.fromisoformat(date_str)

        return CashBalance(
            id=latest["id"],
            date=parsed_date,
            amount=Decimal(str(latest["value"])),
            currency="USD",  # Will be overridden by caller
        )
