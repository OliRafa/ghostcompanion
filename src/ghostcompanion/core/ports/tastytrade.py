from abc import ABC, abstractmethod

from tastytrade.account import Transaction


class TastytradePort(ABC):
    @abstractmethod
    def get_trades_history(self) -> list[Transaction]:
        """Returns raw transaction history from Tastytrade API"""
        ...
