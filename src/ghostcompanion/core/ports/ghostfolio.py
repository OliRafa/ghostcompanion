from abc import ABC, abstractmethod
from datetime import date
from decimal import Decimal
from typing import Any


class GhostfolioPort(ABC):
    @abstractmethod
    def create_account(self, account_data: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    def delete_order_by_id(self, order_id: str):
        ...

    @abstractmethod
    def get_accounts(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_orders(self, account_id: str | None = None) -> dict:
        ...

    @abstractmethod
    def insert_orders(self, orders: list[dict[str, str | float]]):
        ...

    # Cash Balance Methods
    @abstractmethod
    def get_account_balances(self, account_id: str) -> list[dict]:
        """
        Returns existing cash balances for account.
        Format: [{"id": "uuid", "date": "2024-01-15", "value": 1250.50}, ...]
        """
        ...

    @abstractmethod
    def create_account_balance(
        self, account_id: str, date: date, value: Decimal
    ) -> dict:
        """Creates a new cash balance entry for specific date"""
        ...
