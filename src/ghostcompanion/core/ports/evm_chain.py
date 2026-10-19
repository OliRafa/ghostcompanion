from abc import ABC, abstractmethod
from typing import Any, Literal

from ghostcompanion.core.entity.wallet import Network


class EvmChainPort(ABC):
    @abstractmethod
    def get_asset_transfers(
        self, network: Network, address: str, direction: Literal["from", "to"]
    ) -> list[dict[str, Any]]:
        """Returns every native-coin and ERC-20 transfer sent from (or to) the
        address, in Alchemy's `alchemy_getAssetTransfers` format."""
        ...

    @abstractmethod
    def get_transaction_receipts(
        self, network: Network, transaction_hashes: list[str]
    ) -> list[dict[str, Any]]:
        """Returns the receipts of the given transactions."""
        ...
