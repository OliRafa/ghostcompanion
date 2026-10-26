from abc import ABC, abstractmethod
from typing import Any

from ghostcompanion.core.entity.lending import (
    LendingChange,
    LendingPosition,
    LendingReserve,
)
from ghostcompanion.core.entity.wallet import Network


class LendingMarketPort(ABC):
    @abstractmethod
    def get_reserves(self, network: Network, assets: list[str]) -> list[LendingReserve]:
        """Returns the reserves the market keeps for the given coins, by
        contract, leaving out the coins it doesn't lend."""
        ...

    @abstractmethod
    def get_positions(
        self, network: Network, owner: str, reserves: list[LendingReserve]
    ) -> list[LendingPosition]:
        """Returns what the owner has supplied to and borrowed from each reserve
        right now, interest included."""
        ...

    @abstractmethod
    def get_changes(
        self, owner: str, reserves: list[LendingReserve], receipt: dict[str, Any]
    ) -> list[LendingChange]:
        """Returns what the transaction behind the receipt did to the owner's
        position in each of the reserves it touched, whoever signed it."""
        ...
