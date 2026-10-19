from typing import Any, Literal

from ghostcompanion.core.entity.wallet import Network
from ghostcompanion.core.ports.evm_chain import EvmChainPort
from tests.resources.evm.transfers import BASE_TRANSFERS, ETHEREUM_TRANSFERS, RECEIPTS


class InMemoryEvmChainApi(EvmChainPort):
    def __init__(
        self,
        transfers: dict[Network, list[dict[str, Any]]] | None = None,
        receipts: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._transfers = (
            {Network.BASE: BASE_TRANSFERS, Network.ETHEREUM: ETHEREUM_TRANSFERS}
            if transfers is None
            else transfers
        )
        self._receipts = RECEIPTS if receipts is None else receipts
        self.receipt_requests: list[str] = []

    def get_asset_transfers(
        self, network: Network, address: str, direction: Literal["from", "to"]
    ) -> list[dict[str, Any]]:
        return [
            transfer
            for transfer in self._transfers.get(network, [])
            if (transfer[direction] or "").lower() == address.lower()
        ]

    def get_transaction_receipts(
        self, network: Network, transaction_hashes: list[str]
    ) -> list[dict[str, Any]]:
        self.receipt_requests += transaction_hashes
        return [
            self._receipts[transaction_hash] for transaction_hash in transaction_hashes
        ]
