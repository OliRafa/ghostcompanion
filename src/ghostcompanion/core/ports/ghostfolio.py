from abc import ABC, abstractmethod
from typing import Any


class GhostfolioPort(ABC):
    @abstractmethod
    def create_account(self, account_data: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def delete_order_by_id(self, order_id: str): ...

    @abstractmethod
    def get_accounts(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_orders(self, account_id: str | None = None) -> dict: ...

    @abstractmethod
    def insert_orders(self, orders: list[dict[str, str | float]]): ...
