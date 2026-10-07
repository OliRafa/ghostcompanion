from typing import Any

from ghostcompanion.core.ports.blockchain import BlockchainPort
from tests.resources.blockchain.transactions import TRANSACTIONS


class InMemoryBlockchainApi(BlockchainPort):
    def __init__(self, transactions: list[dict[str, Any]] | None = None) -> None:
        self._transactions = TRANSACTIONS if transactions is None else transactions

    def get_address_transactions(self, address: str) -> list[dict[str, Any]]:
        return [
            transaction
            for transaction in self._transactions
            if address in self._addresses_of(transaction)
        ]

    @staticmethod
    def _addresses_of(transaction: dict[str, Any]) -> set[str]:
        outputs = [vin["prevout"] for vin in transaction["vin"] if vin["prevout"]]
        outputs += transaction["vout"]
        return {output.get("scriptpubkey_address") for output in outputs}
