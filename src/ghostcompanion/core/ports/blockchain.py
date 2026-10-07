from abc import ABC, abstractmethod
from typing import Any


class BlockchainPort(ABC):
    @abstractmethod
    def get_address_transactions(self, address: str) -> list[dict[str, Any]]:
        """Returns the address' confirmed transactions, in Esplora's format."""
        ...
