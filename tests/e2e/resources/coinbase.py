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
        "id": "399a0f9b-61e2-4a40-87fb-4834b565630b",
        "name": "BTC Wallet",
        "type": "wallet",
        "balance": {"amount": "0.00600000", "currency": "BTC"},
        "created_at": "2020-01-04T00:00:00Z",
        "updated_at": "2020-07-17T09:45:00Z",
        "currency": {"code": "BTC", "name": "Bitcoin", "type": "crypto"},
    },
    {
        "id": "bf8ee29d-4616-4a9a-b239-1245db792793",
        "name": "ETH Wallet",
        "type": "wallet",
        "balance": {"amount": "1.50000000", "currency": "ETH"},
        "created_at": "2020-01-30T14:22:00Z",
        "updated_at": "2020-07-04T02:34:00Z",
        "currency": {"code": "ETH", "name": "Ethereum", "type": "crypto"},
    },
    {
        "id": "69cb3aef-f5f8-44c4-baaa-0ece8c2a16bb",
        "name": "USD Wallet",
        "type": "fiat",
        "balance": {"amount": "0.00", "currency": "USD"},
        "created_at": "2020-01-17T07:11:00Z",
        "updated_at": "2020-07-30T16:56:00Z",
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
        "created_at": "2020-05-26T05:01:00Z",
        "id": "58ecb957-e5b7-4048-a853-4e9461a97a2e",
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
        "created_at": "2020-06-08T12:12:00Z",
        "id": "4c99e677-bf47-4d32-989a-5f8f12640413",
        "native_amount": {"amount": "150.00", "currency": "USD"},
        "status": "completed",
        "type": "buy",
    },
    {
        "amount": {"amount": "-0.00200000", "currency": "BTC"},
        "created_at": "2020-06-21T19:23:00Z",
        "id": "a76628f7-81c3-4e87-b399-9ab36f3d9a81",
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
        "created_at": "2020-04-17T08:28:00Z",
        "id": "3f9ac490-1823-4f52-b743-ca0515396b44",
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
