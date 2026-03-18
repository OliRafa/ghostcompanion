from abc import ABC, abstractmethod
from decimal import Decimal

from tastytrade.account import Transaction


class TastytradePort(ABC):
    @abstractmethod
    def get_trades_history(self) -> list[Transaction]:
        """Returns raw transaction history from Tastytrade API"""
        ...

    @abstractmethod
    def get_current_cash_balance(self) -> Decimal:
        """Returns the current cash balance from the account.

        This is a snapshot of the current cash position, not calculated
        from transaction history.
        """
        ...
