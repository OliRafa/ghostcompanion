from decimal import Decimal
from typing import Any

from ghostcompanion.core.entity.lending import (
    LendingChange,
    LendingPosition,
    LendingReserve,
)
from ghostcompanion.core.entity.wallet import Network
from ghostcompanion.core.ports.lending_market import LendingMarketPort
from tests.resources.evm.transfers import AAVE_CHANGES, AAVE_RESERVES


class InMemoryLendingMarketApi(LendingMarketPort):
    def __init__(
        self,
        reserves: list[LendingReserve] | None = None,
        changes: dict[str, list[LendingChange]] | None = None,
    ) -> None:
        self._reserves = AAVE_RESERVES if reserves is None else reserves
        self._changes = AAVE_CHANGES if changes is None else changes
        self._positions: dict[tuple[str, str], tuple[Decimal, Decimal]] = {}
        self.reserve_requests: list[Network] = []

    def set_position(
        self, owner: str, asset: str, supplied: str = "0", borrowed: str = "0"
    ) -> None:
        self._positions[(owner.lower(), asset)] = (Decimal(supplied), Decimal(borrowed))

    def get_reserves(self, network: Network, assets: list[str]) -> list[LendingReserve]:
        self.reserve_requests.append(network)
        return [
            reserve
            for reserve in self._reserves
            if reserve.network == network and reserve.asset in assets
        ]

    def get_positions(
        self, network: Network, owner: str, reserves: list[LendingReserve]
    ) -> list[LendingPosition]:
        positions = []
        for reserve in reserves:
            supplied, borrowed = self._positions.get(
                (owner.lower(), reserve.asset), (Decimal("0"), Decimal("0"))
            )
            positions.append(
                LendingPosition(reserve=reserve, supplied=supplied, borrowed=borrowed)
            )
        return positions

    def get_changes(
        self, owner: str, reserves: list[LendingReserve], receipt: dict[str, Any]
    ) -> list[LendingChange]:
        return [
            change
            for change in self._changes.get(receipt["transactionHash"], [])
            if change.reserve in reserves
        ]
