import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from ghostcompanion.core.entity.onchain_movement import OnChainMovement
from ghostcompanion.core.entity.wallet import Wallet
from ghostcompanion.core.ports.blockchain import BlockchainPort
from ghostcompanion.core.ports.market_prices import MarketPricePort

logger = logging.getLogger(__name__)

_SATOSHIS_PER_BITCOIN = Decimal("100000000")
_CURRENCY = "USD"


class BlockchainProvider:
    def __init__(self, blockchain_api: BlockchainPort, market_prices: MarketPricePort):
        self.blockchain_api = blockchain_api
        self.market_prices = market_prices

    def get_movements(self, wallet: Wallet) -> list[OnChainMovement]:
        transactions: dict[str, dict[str, Any]] = {}
        for address in wallet.addresses:
            for transaction in self.blockchain_api.get_address_transactions(address):
                if transaction["status"]["confirmed"]:
                    transactions[transaction["txid"]] = transaction

        return [
            self._adapt_transaction(wallet, transaction)
            for transaction in sorted(
                transactions.values(), key=lambda x: x["status"]["block_time"]
            )
        ]

    def _adapt_transaction(
        self, wallet: Wallet, transaction: dict[str, Any]
    ) -> OnChainMovement:
        inputs = [vin["prevout"] for vin in transaction["vin"] if vin.get("prevout")]
        own_inputs = [x for x in inputs if self._is_owned(wallet, x)]
        foreign_inputs = [x for x in inputs if not self._is_owned(wallet, x)]
        outputs = transaction["vout"]

        spent = sum(output["value"] for output in own_inputs)
        received = sum(x["value"] for x in outputs if self._is_owned(wallet, x))
        fee = 0
        if own_inputs:
            fee = transaction["fee"]
            if foreign_inputs:
                self._warn_about_foreign_inputs(wallet, transaction, foreign_inputs)
                total_input = sum(x["value"] for x in inputs)
                fee = round(transaction["fee"] * spent / total_input)

        external_addresses = {
            x["scriptpubkey_address"]
            for x in outputs
            if x.get("scriptpubkey_address") and not self._is_owned(wallet, x)
        }
        executed_at = datetime.fromtimestamp(
            transaction["status"]["block_time"], tz=timezone.utc
        )

        return OnChainMovement(
            account=wallet.name,
            currency=_CURRENCY,
            destination_address=(
                next(iter(external_addresses))
                if own_inputs and len(external_addresses) == 1
                else None
            ),
            executed_at=executed_at,
            fee=self._to_coins(fee),
            market_unit_price=self.market_prices.get_crypto_price(
                wallet.symbol, _CURRENCY, executed_at.date()
            ),
            quantity=self._to_coins(received - spent + fee),
            symbol=wallet.symbol,
            transaction_id=transaction["txid"],
        )

    @staticmethod
    def _is_owned(wallet: Wallet, output: dict[str, Any]) -> bool:
        address = output.get("scriptpubkey_address")
        return address is not None and wallet.owns(address)

    @staticmethod
    def _to_coins(satoshis: int) -> Decimal:
        return Decimal(satoshis) / _SATOSHIS_PER_BITCOIN

    @staticmethod
    def _warn_about_foreign_inputs(
        wallet: Wallet, transaction: dict[str, Any], foreign_inputs: list[dict]
    ):
        addresses = sorted(
            {
                output.get("scriptpubkey_address", "?")[:8] + "…"
                for output in foreign_inputs
            }
        )
        logger.warning(
            f"Transaction {transaction['txid']} spends from `{wallet.name}` together"
            f" with addresses not listed for it ({', '.join(addresses)}). If those"
            " belong to the wallet (e.g. change addresses), add them to the config,"
            " or its balance will be off."
        )
