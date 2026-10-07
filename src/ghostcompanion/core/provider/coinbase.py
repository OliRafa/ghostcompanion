from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Iterable

from ghostcompanion.core.entity.cash_balance import CashBalance
from ghostcompanion.core.entity.onchain_movement import OnChainMovement
from ghostcompanion.core.entity.trade import Trade
from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.ports.coinbase import CoinbasePort


def _parse_created_at(transaction: dict[str, Any]) -> datetime:
    return datetime.strptime(transaction["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )


class CoinbaseProvider:
    ACCOUNT_NAME = "Coinbase"

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
                case _ if self._is_coinbase_earn(transaction):
                    trades.append(self._adapt_coinbase_earn(transaction))
                case _ if self._is_trade(transaction):
                    trades.append(self._adapt_trade(transaction))
                case _ if self._is_buy_or_sell(transaction):
                    trades.append(self._adapt_buy_sell(transaction))
                case _:
                    continue

        return trades

    def get_movements(self, coin: str) -> list[OnChainMovement]:
        """Coins sent from or received into Coinbase, which may be transfers from or
        to the user's own wallets."""
        movements = []
        for transaction in self.coinbase_api.get_transactions(coin):
            if (
                transaction["type"] == "send"
                and transaction["status"] == "completed"
                and not self._is_coinbase_earn(transaction)
                and Decimal(transaction["amount"]["amount"]) != 0
            ):
                movements += self._adapt_send(transaction)

        return movements

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

    @classmethod
    def _adapt_send(cls, transaction: dict[str, Any]) -> list[OnChainMovement]:
        amount = Decimal(transaction["amount"]["amount"])
        symbol = transaction["amount"]["currency"]
        executed_at = _parse_created_at(transaction)
        network = transaction.get("network") or {}
        transaction_fee = network.get("transaction_fee")

        # A send's amount already includes the network fee Coinbase charged, so
        # the receiving side got that much less.
        fee = Decimal("0")
        fee_movements = []
        if amount < 0 and transaction_fee:
            if transaction_fee["currency"] == symbol:
                fee = Decimal(transaction_fee["amount"])
            else:
                fee_movements.append(
                    OnChainMovement(
                        account=cls.ACCOUNT_NAME,
                        currency=transaction["native_amount"]["currency"],
                        executed_at=executed_at,
                        fee=Decimal(transaction_fee["amount"]),
                        market_unit_price=Decimal("0"),
                        quantity=Decimal("0"),
                        symbol=transaction_fee["currency"],
                    )
                )

        transaction_hash = network.get("hash")
        movement = OnChainMovement(
            account=cls.ACCOUNT_NAME,
            currency=transaction["native_amount"]["currency"],
            destination_address=(
                (transaction.get("to") or {}).get("address") if amount < 0 else None
            ),
            executed_at=executed_at,
            fee=fee,
            market_unit_price=abs(Decimal(transaction["native_amount"]["amount"]))
            / abs(amount),
            quantity=amount + fee if amount < 0 else amount,
            symbol=symbol,
            transaction_id=transaction_hash.lower() if transaction_hash else None,
        )

        return [movement] + fee_movements

    @staticmethod
    def _is_trade(transaction: dict[str, Any]) -> bool:
        return True if transaction["type"] == "trade" else False

    @staticmethod
    def _adapt_buy_sell(transaction: dict[str, Any]) -> Trade:
        transaction_type = transaction["type"]

        return Trade(
            currency=transaction[transaction_type]["total"]["currency"],
            executed_at=_parse_created_at(transaction),
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
            executed_at=_parse_created_at(transaction),
            fee=Decimal("0"),
            quantity=abs(Decimal(transaction["amount"]["amount"])),
            symbol=transaction["amount"]["currency"],
            transaction_type=TransactionType["BUY"],
            value=Decimal("0"),
        )

    @staticmethod
    def _adapt_trade(transaction: dict[str, Any]) -> Trade:
        amount = Decimal(transaction["amount"]["amount"])

        transaction_type = "sell" if amount < 0 else "buy"

        return Trade(
            currency=transaction["native_amount"]["currency"],
            executed_at=_parse_created_at(transaction),
            fee=Decimal("0"),
            quantity=abs(amount),
            symbol=transaction["amount"]["currency"],
            transaction_type=TransactionType[transaction_type.upper()],
            value=abs(Decimal(transaction["native_amount"]["amount"])),
        )

    # Cash Balance Methods

    def get_current_cash_balance(self, currency: str = "USD") -> CashBalance:
        """Get the current cash balance from Coinbase account.

        Returns a single CashBalance with today's date and the current
        cash amount from fiat accounts matching the specified currency.

        Args:
            currency: The account currency (default "USD")

        Returns:
            CashBalance with today's date and current cash amount
        """
        cash_amount = self.coinbase_api.get_current_cash_balance(currency)
        return CashBalance(date=date.today(), amount=cash_amount, currency=currency)
