"""Deterministic Base data for the Aave end-to-end tests: the "DeFi Wallet" gets
1000 USDC, supplies 600 of it to Aave and withdraws 200. Only Yahoo-priced coins,
so any Ghostfolio can import them; debts need the price proxy, so none here."""

from decimal import Decimal
from typing import Any

from ghostcompanion.core.entity.lending import LendingChange, LendingReserve
from ghostcompanion.core.entity.wallet import Network

WALLET = "0x2222222222222222222222222222222222222222"
SENDER = "0x4444444444444444444444444444444444444444"
AAVE_POOL = "0xa238dd80c259a72e81d7e4664a9801593f98d1c5"
USDC_BASE = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
A_USDC = "0x4e65fe4dba92790696d040ac24aa414708f5c0ab"
DEBT_USDC = "0x59dca05b6c26dbd64b5381374aaac5cd05644c28"
NO_ADDRESS = "0x" + "0" * 40

DEPOSIT = "0x" + "f1" * 32
SUPPLY = "0x" + "f2" * 32
WITHDRAW = "0x" + "f3" * 32

USDC_RESERVE = LendingReserve(
    network=Network.BASE,
    asset=USDC_BASE,
    supply_token=A_USDC,
    debt_token=DEBT_USDC,
    decimals=6,
)


def _transfer(
    transaction_hash: str,
    timestamp: str,
    category: str,
    sender: str,
    receiver: str,
    usdc: int = 0,
    contract: str | None = None,
    index: int = 0,
) -> dict[str, Any]:
    return {
        "uniqueId": f"{transaction_hash}:{index}",
        "hash": transaction_hash,
        "category": category,
        "from": sender,
        "to": receiver,
        "rawContract": {
            "value": hex(usdc * 10**6),
            "address": contract,
            "decimal": hex(6 if contract else 18),
        },
        "metadata": {"blockTimestamp": timestamp},
    }


TRANSFERS: list[dict[str, Any]] = [
    _transfer(
        DEPOSIT, "2026-04-02T19:00:00.000Z", "erc20", SENDER, WALLET, 1000, USDC_BASE
    ),
    _transfer(SUPPLY, "2026-04-03T19:00:00.000Z", "external", WALLET, AAVE_POOL),
    _transfer(
        SUPPLY, "2026-04-03T19:00:00.000Z", "erc20", WALLET, A_USDC, 600, USDC_BASE, 1
    ),
    _transfer(
        SUPPLY, "2026-04-03T19:00:00.000Z", "erc20", NO_ADDRESS, WALLET, 600, A_USDC, 2
    ),
    _transfer(WITHDRAW, "2026-04-04T19:00:00.000Z", "external", WALLET, AAVE_POOL),
    _transfer(
        WITHDRAW,
        "2026-04-04T19:00:00.000Z",
        "erc20",
        WALLET,
        NO_ADDRESS,
        200,
        A_USDC,
        1,
    ),
    _transfer(
        WITHDRAW, "2026-04-04T19:00:00.000Z", "erc20", A_USDC, WALLET, 200, USDC_BASE, 2
    ),
]

# What Aave's events in the receipts say the supply and the withdrawal did.
CHANGES: dict[str, list[LendingChange]] = {
    SUPPLY: [LendingChange(reserve=USDC_RESERVE, supplied=Decimal("600"))],
    WITHDRAW: [LendingChange(reserve=USDC_RESERVE, supplied=Decimal("-200"))],
}

RECEIPTS: dict[str, dict[str, Any]] = {
    transaction_hash: {
        "transactionHash": transaction_hash,
        "from": WALLET,
        "status": "0x1",
        "gasUsed": hex(100_000),
        "effectiveGasPrice": hex(10**9),
        "l1Fee": hex(0),
    }
    for transaction_hash in (SUPPLY, WITHDRAW)
}
