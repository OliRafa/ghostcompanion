"""Deterministic in-memory Coinbase source data for end-to-end tests.

The *source* side (Coinbase) is stubbed so runs are repeatable and need no
secrets; only the *sink* (Ghostfolio) is real.

Ghostfolio validates every activity symbol against its data source (YAHOO). The
import use case turns each coin code into a crypto pair via
``adapt_crypto_symbol`` (``BTC`` -> ``BTCUSD``); YAHOO accepts that ``<COIN>USD``
form, so BTC/ETH round-trip cleanly. Values below are synthetic but the ones we
assert on are exactly what our code computes and persists.
"""

from decimal import Decimal
from typing import Any

from ghostcompanion.core.ports.coinbase import CoinbasePort

ACCOUNTS: list[dict[str, Any]] = [
    {
        "id": "2a412400-b1d4-4fe4-bce7-1d05d1ba950c",
        "name": "BTC Wallet",
        "type": "wallet",
        "balance": {"amount": "0.00600000", "currency": "BTC"},
        "created_at": "2021-06-21T15:08:13Z",
        "updated_at": "2024-01-22T21:12:25Z",
        "currency": {"code": "BTC", "name": "Bitcoin", "type": "crypto"},
    },
    {
        "id": "eb727849-0fb3-421f-9193-b4d846acdbdb",
        "name": "ETH Wallet",
        "type": "wallet",
        "balance": {"amount": "1.50000000", "currency": "ETH"},
        "created_at": "2021-06-21T15:57:31Z",
        "updated_at": "2022-09-08T17:25:04Z",
        "currency": {"code": "ETH", "name": "Ethereum", "type": "crypto"},
    },
    {
        "id": "8c7bb50d-353d-45df-93a8-87bf39aa1376",
        "name": "USD Wallet",
        "type": "fiat",
        "balance": {"amount": "0.00", "currency": "USD"},
        "created_at": "2021-06-21T15:08:49Z",
        "updated_at": "2024-08-06T12:00:49Z",
        "currency": {"code": "USD", "name": "US Dollar", "type": "fiat"},
    },
]

TRANSACTIONS: list[dict[str, Any]] = [
    {
        "amount": {"amount": "0.00500000", "currency": "BTC"},
        "buy": {
            "subtotal": {"amount": "200.00", "currency": "USD"},
            "total": {"amount": "200.00", "currency": "USD"},
        },
        "created_at": "2021-11-18T14:48:03Z",
        "id": "a1a78e81-06b3-4a82-8047-5e69b16bfea1",
        "native_amount": {"amount": "200.00", "currency": "USD"},
        "status": "completed",
        "type": "buy",
    },
    {
        "amount": {"amount": "0.00300000", "currency": "BTC"},
        "buy": {
            "fee": {"amount": "3.00", "currency": "USD"},
            "subtotal": {"amount": "150.00", "currency": "USD"},
            "total": {"amount": "153.00", "currency": "USD"},
        },
        "created_at": "2021-11-26T17:09:19Z",
        "id": "854abb28-dc58-4e4e-af82-1968515ea87e",
        "native_amount": {"amount": "150.00", "currency": "USD"},
        "status": "completed",
        "type": "buy",
    },
    {
        "amount": {"amount": "-0.00200000", "currency": "BTC"},
        "created_at": "2022-01-10T09:00:00Z",
        "id": "385fea46-92b1-49a8-879e-e8e10807089b",
        "native_amount": {"amount": "-100.00", "currency": "USD"},
        "sell": {
            "subtotal": {"amount": "100.00", "currency": "USD"},
            "total": {"amount": "100.00", "currency": "USD"},
        },
        "status": "completed",
        "type": "sell",
    },
    {
        "amount": {"amount": "1.50000000", "currency": "ETH"},
        "buy": {
            "subtotal": {"amount": "3000.00", "currency": "USD"},
            "total": {"amount": "3000.00", "currency": "USD"},
        },
        "created_at": "2021-10-06T11:35:29Z",
        "id": "c6b3b74b-d904-4d44-a41a-cc7547827b34",
        "native_amount": {"amount": "3000.00", "currency": "USD"},
        "status": "completed",
        "type": "buy",
    },
]


class InMemoryCoinbaseApi(CoinbasePort):
    def __init__(self, cash_balance: Decimal = Decimal("1000.00")) -> None:
        self._accounts = ACCOUNTS
        self._transactions = TRANSACTIONS
        self._cash_balance = cash_balance

    def set_cash_balance(self, balance: Decimal) -> None:
        self._cash_balance = balance

    def get_current_cash_balance(self, currency: str) -> Decimal:
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
