from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

from ghostcompanion.core.entity.trade import Trade
from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.ports.coinbase import CoinbasePort


class CoinbaseProvider:
    def __init__(self, coinbase_api: CoinbasePort) -> None:
        self.coinbase_api = coinbase_api

    def get_coins(self) -> list[str]:
        coins = self.coinbase_api.get_accounts()
        coins = self._filter_not_traded_coins(coins)
        coins = self._filter_fiat(coins)
        return list(map(lambda x: x["currency"]["code"], coins))

    def get_trades(self, coin: str) -> list[Trade]:
        transactions = self.coinbase_api.get_transactions(coin)

        trades = []
        for transaction in transactions:
            match transaction:
                case _ if self._is_network_fee(transaction):
                    trades.append(self._adapt_network_fee(transaction))
                case _ if self._is_coinbase_earn(transaction):
                    trades.append(self._adapt_coinbase_earn(transaction))
                case _ if self._is_trade(transaction):
                    trades.append(self._adapt_trade(transaction))
                case _ if self._is_buy_or_sell(transaction):
                    trades.append(self._adapt_buy_sell(transaction))
                case _:
                    continue

        return trades

    @staticmethod
    def _filter_not_traded_coins(
        coins: list[dict[str, Any]],
    ) -> Iterable[dict[str, Any]]:
        return filter(
            lambda x: not (
                float(x["balance"]["amount"]) == 0.0
                and x["created_at"] == x["updated_at"]
            ),
            coins,
        )

    @staticmethod
    def _filter_fiat(coins: Iterable[dict[str, Any]]) -> Iterable[dict[str, Any]]:
        return filter(lambda x: not x["type"] == "fiat", coins)

    @staticmethod
    def _is_buy_or_sell(transaction: dict[str, Any]) -> bool:
        return True if transaction["type"] in ("buy", "sell") else False

    @staticmethod
    def _is_coinbase_earn(transaction: dict[str, Any]) -> bool:
        if (
            transaction["type"] == "send"
            and transaction.get("from", {}).get("name", "") == "Coinbase Earn"
        ):
            return True

        return False

    @staticmethod
    def _is_network_fee(transaction: dict[str, Any]) -> bool:
        if (
            transaction["type"] == "send"
            and Decimal(transaction["amount"]["amount"]) < 0
            and transaction.get("network") is not None
            and transaction.get("to") is not None
        ):
            return True

        return False

    @staticmethod
    def _is_trade(transaction: dict[str, Any]) -> bool:
        return True if transaction["type"] == "trade" else False

    @staticmethod
    def _adapt_buy_sell(transaction: dict[str, Any]) -> Trade:
        transaction_type = transaction["type"]

        return Trade(
            currency=transaction[transaction_type]["total"]["currency"],
            executed_at=datetime.strptime(
                transaction["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc),
            fee=Decimal(
                transaction[transaction_type].get("fee", {}).get("amount", "0.0")
            ),
            quantity=abs(Decimal(transaction["amount"]["amount"])),
            symbol=transaction["amount"]["currency"],
            transaction_type=TransactionType[transaction_type.upper()],
            value=abs(Decimal(transaction[transaction_type]["subtotal"]["amount"])),
        )

    @staticmethod
    def _adapt_coinbase_earn(transaction: dict[str, Any]) -> Trade:
        return Trade(
            currency=transaction["native_amount"]["currency"],
            executed_at=datetime.strptime(
                transaction["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc),
            fee=Decimal("0"),
            quantity=abs(Decimal(transaction["amount"]["amount"])),
            symbol=transaction["amount"]["currency"],
            transaction_type=TransactionType["BUY"],
            value=Decimal("0"),
        )

    @staticmethod
    def _adapt_network_fee(transaction: dict[str, Any]) -> Trade:
        return Trade(
            currency=transaction["native_amount"]["currency"],
            description="Network Fee",
            executed_at=datetime.strptime(
                transaction["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc),
            fee=Decimal("0"),
            quantity=abs(Decimal(transaction["network"]["transaction_fee"]["amount"])),
            symbol=transaction["network"]["transaction_fee"]["currency"],
            transaction_type=TransactionType["SELL"],
            value=Decimal("0"),
        )

    @staticmethod
    def _adapt_trade(transaction: dict[str, Any]) -> Trade:
        amount = Decimal(transaction["amount"]["amount"])

        transaction_type = "sell" if amount < 0 else "buy"

        return Trade(
            currency=transaction["native_amount"]["currency"],
            executed_at=datetime.strptime(
                transaction["created_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=timezone.utc),
            fee=Decimal("0"),
            quantity=abs(amount),
            symbol=transaction["amount"]["currency"],
            transaction_type=TransactionType[transaction_type.upper()],
            value=abs(Decimal(transaction["native_amount"]["amount"])),
        )
