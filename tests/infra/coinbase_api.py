from typing import Any

from ghostcompanion.core.ports.coinbase import CoinbasePort
from tests.resources.coinbase.accounts import ACCOUNTS
from tests.resources.coinbase.transactions import TRANSACTIONS


class InMemoryCoinbaseApi(CoinbasePort):
    def __init__(self) -> None:
        self._accounts = ACCOUNTS
        self._transactions = TRANSACTIONS

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
