from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any


class CoinbasePort(ABC):
    @abstractmethod
    def get_current_cash_balance(self, currency: str) -> Decimal:
        """Returns the current cash balance from fiat accounts matching the currency."""
        ...

    @abstractmethod
    def get_accounts(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_transactions(self, coin: str) -> list[dict[str, Any]]:
        ...
