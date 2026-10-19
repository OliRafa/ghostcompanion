"""Deterministic Coinbase and Base data for the EVM wallet end-to-end tests: a
Coinbase USDC withdrawal into the "DeFi Wallet", a swap of USDC for ETH, and a
payment out. Only Yahoo-priced coins, so any Ghostfolio can import them."""

from typing import Any

WALLET = "0x2222222222222222222222222222222222222222"
COINBASE_HOT = "0xc1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1c1"
SWAP_ROUTER = "0x5b5b000000000000000000000000000000000009"
MERCHANT = "0x3f3f00000000000000000000000000000000000a"
USDC_BASE = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"

WITHDRAWAL = "0x" + "e3" * 32
SWAP = "0x" + "e4" * 32
PAYMENT = "0x" + "e5" * 32

USDC_ACCOUNT: dict[str, Any] = {
    "id": "e2e-usdc-account",
    "type": "wallet",
    "balance": {"amount": "0", "currency": "USDC"},
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-04-02T18:20:00Z",
    "currency": {"code": "USDC", "type": "crypto"},
}

COINBASE_TRANSACTIONS: list[dict[str, Any]] = [
    {
        "amount": {"amount": "-1000.000000", "currency": "USDC"},
        "created_at": "2026-04-02T18:20:00Z",
        "native_amount": {"amount": "-1000.00", "currency": "USD"},
        "network": {
            "hash": WITHDRAWAL,
            "network_name": "base",
            "transaction_fee": {"amount": "0.000000", "currency": "USDC"},
        },
        "status": "completed",
        "to": {"address": WALLET, "resource": "address"},
        "type": "send",
    }
]


def _transfer(
    transaction_hash, category, sender, receiver, raw_value, contract=None, index=0
):
    return {
        "uniqueId": f"{transaction_hash}:{index}",
        "hash": transaction_hash,
        "category": category,
        "from": sender,
        "to": receiver,
        "rawContract": {
            "value": hex(raw_value),
            "address": contract,
            "decimal": hex(6 if contract else 18),
        },
        "metadata": {"blockTimestamp": "2026-04-02T19:00:00.000Z"},
    }


TRANSFERS: list[dict[str, Any]] = [
    _transfer(WITHDRAWAL, "erc20", COINBASE_HOT, WALLET, 1000 * 10**6, USDC_BASE),
    _transfer(SWAP, "external", WALLET, SWAP_ROUTER, 0),
    _transfer(SWAP, "erc20", WALLET, SWAP_ROUTER, 400 * 10**6, USDC_BASE, 1),
    # The router pays native ETH back through an internal transfer.
    _transfer(SWAP, "internal", SWAP_ROUTER, WALLET, 2 * 10**17, index=2),
    _transfer(PAYMENT, "external", WALLET, USDC_BASE, 0),
    _transfer(PAYMENT, "erc20", WALLET, MERCHANT, 100 * 10**6, USDC_BASE, 1),
]

RECEIPTS: dict[str, dict[str, Any]] = {
    transaction_hash: {
        "transactionHash": transaction_hash,
        "from": WALLET,
        "status": "0x1",
        "gasUsed": hex(100_000),
        "effectiveGasPrice": hex(10**9),
        "l1Fee": hex(0),
    }
    for transaction_hash in (SWAP, PAYMENT)
}
