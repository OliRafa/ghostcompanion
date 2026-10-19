from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any

from ghostcompanion.core.entity.onchain_movement import OnChainMovement
from ghostcompanion.core.entity.token import Token
from ghostcompanion.core.entity.wallet import Network, Wallet
from ghostcompanion.core.ports.evm_chain import EvmChainPort
from ghostcompanion.core.ports.market_prices import MarketPricePort

_CURRENCY = "USD"
_WEI_PER_ETHER = Decimal(10**18)


class EvmWalletProvider:
    def __init__(self, evm_chain_api: EvmChainPort, market_prices: MarketPricePort):
        self.evm_chain_api = evm_chain_api
        self.market_prices = market_prices

    def get_movements(
        self, wallet: Wallet, tokens: list[Token]
    ) -> list[OnChainMovement]:
        """One movement per transaction and tracked token, net of what came back
        in the same transaction, on every network the wallet spans."""
        movements = []
        for network in wallet.networks:
            tracked = {x.contract: x for x in tokens if x.network == network}
            movements += self._get_network_movements(wallet, network, tracked)

        return sorted(movements, key=lambda x: x.executed_at)

    def _get_network_movements(
        self, wallet: Wallet, network: Network, tracked: dict[str | None, Token]
    ) -> list[OnChainMovement]:
        transfers: dict[str, dict[str, Any]] = {}
        for address in wallet.addresses:
            for direction in ("from", "to"):
                for transfer in self.evm_chain_api.get_asset_transfers(
                    network, address, direction
                ):
                    transfers[transfer["uniqueId"]] = transfer

        by_transaction: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for transfer in transfers.values():
            by_transaction[transfer["hash"].lower()].append(transfer)

        # Every transaction the wallet signs moves its native coin from it, even
        # a zero amount, so these are the ones that may have cost it a fee.
        candidates = sorted(
            transaction_hash
            for transaction_hash, items in by_transaction.items()
            if any(
                x["category"] == "external" and self._owns(wallet, x["from"])
                for x in items
            )
        )
        receipts = {
            receipt["transactionHash"].lower(): receipt
            for receipt in self.evm_chain_api.get_transaction_receipts(
                network, candidates
            )
        }

        movements = []
        for transaction_hash, items in by_transaction.items():
            receipt = receipts.get(transaction_hash)
            movements += self._adapt_transaction(
                wallet, network, tracked, transaction_hash, items, receipt
            )

        return movements

    def _adapt_transaction(
        self,
        wallet: Wallet,
        network: Network,
        tracked: dict[str | None, Token],
        transaction_hash: str,
        transfers: list[dict[str, Any]],
        receipt: dict[str, Any] | None,
    ) -> list[OnChainMovement]:
        signed_by_wallet = receipt is not None and self._owns(wallet, receipt["from"])
        fee = self._fee(receipt) if signed_by_wallet else Decimal("0")
        # A failed transaction moved nothing, but its signer still paid the fee.
        succeeded = receipt is None or receipt["status"] == "0x1"

        quantities: dict[Token, Decimal] = defaultdict(Decimal)
        destinations: dict[Token, set[str]] = defaultdict(set)
        for transfer in transfers if succeeded else []:
            contract = (transfer["rawContract"]["address"] or "").lower() or None
            token = tracked.get(contract)
            amount = self._amount(transfer)
            # Untracked contracts are where lookalike tokens and spam live, and
            # anyone can emit a zero-value transfer in the wallet's name.
            if token is None or amount == 0:
                continue
            if self._owns(wallet, transfer["to"]):
                quantities[token] += amount
            if self._owns(wallet, transfer["from"]):
                quantities[token] -= amount
                if not self._owns(wallet, transfer["to"]):
                    destinations[token].add(transfer["to"].lower())

        native = tracked.get(None)
        if fee > 0 and native is not None:
            quantities.setdefault(native, Decimal("0"))

        executed_at = datetime.fromisoformat(transfers[0]["metadata"]["blockTimestamp"])
        return [
            OnChainMovement(
                account=wallet.name,
                currency=_CURRENCY,
                data_source=token.data_source,
                destination_address=(
                    next(iter(destinations[token]))
                    if len(destinations[token]) == 1
                    else None
                ),
                executed_at=executed_at,
                fee=fee if token is native else Decimal("0"),
                market_unit_price=self._price(token, executed_at),
                quantity=quantity,
                symbol=token.symbol,
                transaction_id=transaction_hash,
            )
            for token, quantity in quantities.items()
            if quantity != 0 or (token is native and fee > 0)
        ]

    def _price(self, token: Token, executed_at: datetime) -> Decimal | None:
        if token.price_symbol is None:
            return None
        return self.market_prices.get_crypto_price(
            token.price_symbol, _CURRENCY, executed_at.date()
        )

    @staticmethod
    def _amount(transfer: dict[str, Any]) -> Decimal:
        raw = transfer["rawContract"]
        return Decimal(int(raw["value"] or "0x0", 16)) / Decimal(10) ** int(
            raw["decimal"] or "0x12", 16
        )

    @staticmethod
    def _fee(receipt: dict[str, Any]) -> Decimal:
        # On Base, a transaction also pays for posting its data to Ethereum.
        wei = int(receipt["gasUsed"], 16) * int(receipt["effectiveGasPrice"], 16)
        wei += int(receipt.get("l1Fee") or "0x0", 16)
        return Decimal(wei) / _WEI_PER_ETHER

    @staticmethod
    def _owns(wallet: Wallet, address: str | None) -> bool:
        return address is not None and wallet.owns(address)
