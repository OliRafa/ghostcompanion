from decimal import Decimal
from typing import Any

from ghostcompanion.core.ports.coinbase import CoinbasePort
from tests.resources.coinbase.accounts import ACCOUNTS
from tests.resources.coinbase.transactions import TRANSACTIONS


class InMemoryCoinbaseApi(CoinbasePort):
    def __init__(self, cash_balance: Decimal = Decimal("1000.00")) -> None:
        self._accounts = ACCOUNTS
        self._transactions = TRANSACTIONS
        self._cash_balance = cash_balance

    def set_cash_balance(self, balance: Decimal) -> None:
        """Set the current cash balance for testing."""
        self._cash_balance = balance

    def get_current_cash_balance(self, currency: str) -> Decimal:
        """Return the current cash balance for testing.

        For testing, we return a simple balance regardless of currency.
        In real scenarios, this would filter fiat accounts by currency.
        """
        return self._cash_balance

    def get_accounts(self) -> list[dict[str, Any]]:
        return self._accounts

    def get_transactions(self, coin: str) -> list[dict[str, Any]]:
        account = next(filter(lambda x: x["currency"]["code"] == coin, self._accounts))
        return list(
            filter(
                lambda x: x["amount"]["currency"] == account["currency"]["code"],
                self._transactions,
            )
        )
