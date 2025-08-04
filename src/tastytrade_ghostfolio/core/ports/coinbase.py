from abc import ABC, abstractmethod
from typing import Any


class CoinbasePort(ABC):
    @abstractmethod
    def get_accounts(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def get_transactions(self, coin: str) -> list[dict[str, Any]]: ...
