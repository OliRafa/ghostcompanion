"""Synthetic Alchemy transfers and receipts around the "DeFi Wallet", modelled on
real activity: Coinbase deposits, a vault deposit, a swap, and the address
poisoning these wallets attract (lookalike tokens, zero-value spoofs, dust).
Aave's supply, borrow, repay and withdraw are kept apart, in AAVE_TRANSFERS, and
so is what relayers do to the position, in AAVE_RELAYED_TRANSFERS."""

from decimal import Decimal
from typing import Any

from ghostcompanion.core.entity.lending import LendingChange, LendingReserve
from ghostcompanion.core.entity.wallet import Network

WALLET = "0x1111111111111111111111111111111111111111"
COINBASE_HOT = "0xc0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0c0"
VAULT_ROUTER = "0xdede000000000000000000000000000000000001"
SWAP_POOL = "0x5a5a000000000000000000000000000000000002"
BRIDGE = "0xb1b1000000000000000000000000000000000003"
MERCHANT = "0x3e3e000000000000000000000000000000000004"
ATTACKER = "0xbad0000000000000000000000000000000000005"
# Shares the first and last characters of MERCHANT, to be copied by mistake.
MERCHANT_LOOKALIKE = "0x3e3e999999999999999999999999999999990004"
COINBASE_DEPOSIT = "0xc0de000000000000000000000000000000000006"
COW_SETTLEMENT = "0x9008d19f58aabd9ed0d60971565aa8510560ab41"
REPAY_ADAPTER = "0xada0000000000000000000000000000000000012"
RELAYER = "0x4e1a000000000000000000000000000000000013"

USDC_BASE = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
CBBTC = "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf"
VAULT_SHARE = "0x3764f07752384450576c6d8b027d06ffa29e5ae9"
FAKE_USDC = "0xfa4e000000000000000000000000000000000007"
SPAM = "0x5ba4000000000000000000000000000000000008"

NO_ADDRESS = "0x" + "0" * 40
AAVE_POOL = "0xa238dd80c259a72e81d7e4664a9801593f98d1c5"
A_USDC = "0x4e65fe4dba92790696d040ac24aa414708f5c0ab"
DEBT_USDC = "0x59dca05b6c26dbd64b5381374aaac5cd05644c28"
A_CBBTC = "0xbdb9300b7cde636d9cd4aff00f6f009ffbbc8ee6"
DEBT_CBBTC = "0xdeb7000000000000000000000000000000000011"

COINBASE_USDC_DEPOSIT = "0x" + "a1" * 32
COINBASE_ETH_DEPOSIT = "0x" + "a2" * 32
APPROVAL = "0x" + "a3" * 32
VAULT_DEPOSIT = "0x" + "a4" * 32
SWAP = "0x" + "a5" * 32
POISON_FAKE_TOKEN = "0x" + "a6" * 32
POISON_ZERO_VALUE = "0x" + "a7" * 32
POISON_DUST = "0x" + "a8" * 32
SPAM_AIRDROP = "0x" + "a9" * 32
BRIDGE_PAYOUT = "0x" + "aa" * 32
FAILED = "0x" + "ab" * 32
PAYMENT = "0x" + "ac" * 32
ETHEREUM_SEND_TO_COINBASE = "0x" + "b1" * 32
AAVE_SUPPLY = "0x" + "c1" * 32
AAVE_BORROW = "0x" + "c2" * 32
AAVE_REPAY = "0x" + "c3" * 32
AAVE_WITHDRAW = "0x" + "c4" * 32
AAVE_REPAY_MINTING_DEBT = "0x" + "c5" * 32
AAVE_COLLATERAL_SWAP = "0x" + "c6" * 32
AAVE_REPAY_WITH_COLLATERAL = "0x" + "c7" * 32

_UNITS = {
    USDC_BASE: 6,
    CBBTC: 8,
    VAULT_SHARE: 18,
    FAKE_USDC: 6,
    SPAM: 18,
    A_USDC: 6,
    DEBT_USDC: 6,
    A_CBBTC: 8,
    None: 18,
}


def _transfer(
    transaction_hash: str,
    timestamp: str,
    category: str,
    sender: str,
    receiver: str,
    amount: str,
    contract: str | None = None,
    index: int = 0,
) -> dict[str, Any]:
    decimals = _UNITS[contract]
    integer, _, fraction = amount.partition(".")
    raw = int(integer + fraction.ljust(decimals, "0")[:decimals])
    return {
        "uniqueId": f"{transaction_hash}:{category}:{index}",
        "hash": transaction_hash,
        "category": category,
        "from": sender,
        "to": receiver,
        "value": float(amount),
        "asset": "ETH" if contract is None else "TOKEN",
        "rawContract": {
            "value": hex(raw),
            "address": contract,
            "decimal": hex(decimals),
        },
        "metadata": {"blockTimestamp": timestamp},
    }


def _receipt(
    transaction_hash: str, sender: str, gas_used: int, l1_fee: int = 0, ok=True
) -> dict[str, Any]:
    return {
        "transactionHash": transaction_hash,
        "from": sender,
        "status": "0x1" if ok else "0x0",
        "gasUsed": hex(gas_used),
        # 1 gwei: gas_used * 1e9 wei.
        "effectiveGasPrice": hex(10**9),
        "l1Fee": hex(l1_fee),
    }


BASE_TRANSFERS: list[dict[str, Any]] = [
    _transfer(
        COINBASE_ETH_DEPOSIT,
        "2026-04-02T18:20:00.000Z",
        "external",
        COINBASE_HOT,
        WALLET,
        "0.004",
    ),
    _transfer(
        COINBASE_USDC_DEPOSIT,
        "2026-04-02T18:23:00.000Z",
        "erc20",
        COINBASE_HOT,
        WALLET,
        "1000",
        USDC_BASE,
    ),
    _transfer(APPROVAL, "2026-04-02T18:30:00.000Z", "external", WALLET, USDC_BASE, "0"),
    _transfer(
        VAULT_DEPOSIT, "2026-04-02T18:35:00.000Z", "external", WALLET, VAULT_ROUTER, "0"
    ),
    _transfer(
        VAULT_DEPOSIT,
        "2026-04-02T18:35:00.000Z",
        "erc20",
        WALLET,
        VAULT_ROUTER,
        "500",
        USDC_BASE,
        1,
    ),
    _transfer(
        VAULT_DEPOSIT,
        "2026-04-02T18:35:00.000Z",
        "erc20",
        "0x" + "0" * 40,
        WALLET,
        "480",
        VAULT_SHARE,
        2,
    ),
    _transfer(SWAP, "2026-04-02T19:00:00.000Z", "external", WALLET, SWAP_POOL, "0"),
    _transfer(
        SWAP,
        "2026-04-02T19:00:00.000Z",
        "erc20",
        WALLET,
        SWAP_POOL,
        "340",
        USDC_BASE,
        1,
    ),
    _transfer(
        SWAP, "2026-04-02T19:00:00.000Z", "erc20", SWAP_POOL, WALLET, "0.005", CBBTC, 2
    ),
    # Emitted by the fake token's own contract: the wallet signed nothing.
    _transfer(
        POISON_FAKE_TOKEN,
        "2026-04-03T10:00:00.000Z",
        "erc20",
        WALLET,
        MERCHANT_LOOKALIKE,
        "340",
        FAKE_USDC,
    ),
    # A zero-value transferFrom anyone can make in the wallet's name.
    _transfer(
        POISON_ZERO_VALUE,
        "2026-04-03T10:01:00.000Z",
        "erc20",
        WALLET,
        MERCHANT_LOOKALIKE,
        "0",
        USDC_BASE,
    ),
    _transfer(
        POISON_DUST,
        "2026-04-03T10:02:00.000Z",
        "erc20",
        MERCHANT_LOOKALIKE,
        WALLET,
        "0.000011",
        USDC_BASE,
    ),
    _transfer(
        SPAM_AIRDROP,
        "2026-04-03T11:00:00.000Z",
        "erc20",
        ATTACKER,
        WALLET,
        "9000",
        SPAM,
    ),
    _transfer(
        BRIDGE_PAYOUT, "2026-04-04T09:00:00.000Z", "internal", BRIDGE, WALLET, "0.001"
    ),
    _transfer(FAILED, "2026-04-05T09:00:00.000Z", "external", WALLET, SWAP_POOL, "0"),
    _transfer(
        FAILED,
        "2026-04-05T09:00:00.000Z",
        "erc20",
        WALLET,
        SWAP_POOL,
        "100",
        USDC_BASE,
        1,
    ),
    _transfer(PAYMENT, "2026-04-06T09:00:00.000Z", "external", WALLET, USDC_BASE, "0"),
    _transfer(
        PAYMENT,
        "2026-04-06T09:00:00.000Z",
        "erc20",
        WALLET,
        MERCHANT,
        "60",
        USDC_BASE,
        1,
    ),
]

ETHEREUM_TRANSFERS: list[dict[str, Any]] = [
    _transfer(
        ETHEREUM_SEND_TO_COINBASE,
        "2024-01-05T18:45:00.000Z",
        "external",
        WALLET,
        COINBASE_DEPOSIT,
        "0.06",
    ),
]

AAVE_RESERVES = [
    LendingReserve(
        network=Network.BASE,
        asset=USDC_BASE,
        supply_token=A_USDC,
        debt_token=DEBT_USDC,
        decimals=6,
    ),
    LendingReserve(
        network=Network.BASE,
        asset=CBBTC,
        supply_token=A_CBBTC,
        debt_token=DEBT_CBBTC,
        decimals=8,
    ),
]


def _aave_call(transaction_hash: str, timestamp: str) -> dict[str, Any]:
    return _transfer(transaction_hash, timestamp, "external", WALLET, AAVE_POOL, "0")


# The pool takes the coin into its supply token's contract and mints that token
# to the wallet, or pays the coin out of it and mints debt; reversed to repay or
# withdraw. A mint or burn carries the interest accrued since the last one, so
# its amount drifts from the coin's.
AAVE_TRANSFERS: list[dict[str, Any]] = [
    _aave_call(AAVE_SUPPLY, "2026-04-07T09:00:00.000Z"),
    _transfer(
        AAVE_SUPPLY,
        "2026-04-07T09:00:00.000Z",
        "erc20",
        WALLET,
        A_CBBTC,
        "0.004",
        CBBTC,
        1,
    ),
    _transfer(
        AAVE_SUPPLY,
        "2026-04-07T09:00:00.000Z",
        "erc20",
        NO_ADDRESS,
        WALLET,
        "0.004",
        A_CBBTC,
        2,
    ),
    _aave_call(AAVE_BORROW, "2026-04-07T09:05:00.000Z"),
    _transfer(
        AAVE_BORROW,
        "2026-04-07T09:05:00.000Z",
        "erc20",
        NO_ADDRESS,
        WALLET,
        "150",
        DEBT_USDC,
        1,
    ),
    _transfer(
        AAVE_BORROW,
        "2026-04-07T09:05:00.000Z",
        "erc20",
        A_USDC,
        WALLET,
        "150",
        USDC_BASE,
        2,
    ),
    _aave_call(AAVE_REPAY, "2026-04-08T09:00:00.000Z"),
    _transfer(
        AAVE_REPAY,
        "2026-04-08T09:00:00.000Z",
        "erc20",
        WALLET,
        A_USDC,
        "50",
        USDC_BASE,
        1,
    ),
    _transfer(
        AAVE_REPAY,
        "2026-04-08T09:00:00.000Z",
        "erc20",
        WALLET,
        NO_ADDRESS,
        "49.98",
        DEBT_USDC,
        2,
    ),
    _aave_call(AAVE_REPAY_MINTING_DEBT, "2026-04-08T10:00:00.000Z"),
    _transfer(
        AAVE_REPAY_MINTING_DEBT,
        "2026-04-08T10:00:00.000Z",
        "erc20",
        WALLET,
        A_USDC,
        "0.01",
        USDC_BASE,
        1,
    ),
    _transfer(
        AAVE_REPAY_MINTING_DEBT,
        "2026-04-08T10:00:00.000Z",
        "erc20",
        NO_ADDRESS,
        WALLET,
        "0.005",
        DEBT_USDC,
        2,
    ),
    _aave_call(AAVE_WITHDRAW, "2026-04-09T09:00:00.000Z"),
    _transfer(
        AAVE_WITHDRAW,
        "2026-04-09T09:00:00.000Z",
        "erc20",
        WALLET,
        NO_ADDRESS,
        "0.001",
        A_CBBTC,
        1,
    ),
    _transfer(
        AAVE_WITHDRAW,
        "2026-04-09T09:00:00.000Z",
        "erc20",
        A_CBBTC,
        WALLET,
        "0.001",
        CBBTC,
        2,
    ),
]

# Relayers act on the position without the wallet's coins or signature: a
# collateral swap CoW Protocol settles, and an adapter selling collateral to repay
# a debt, sending what's left of it to the wallet. Only the market's tokens move.
AAVE_RELAYED_TRANSFERS: list[dict[str, Any]] = [
    _transfer(
        AAVE_COLLATERAL_SWAP,
        "2026-04-10T09:00:00.000Z",
        "erc20",
        WALLET,
        COW_SETTLEMENT,
        "0.001",
        A_CBBTC,
        1,
    ),
    _transfer(
        AAVE_COLLATERAL_SWAP,
        "2026-04-10T09:00:00.000Z",
        "erc20",
        NO_ADDRESS,
        WALLET,
        "0.00000002",
        A_CBBTC,
        2,
    ),
    _transfer(
        AAVE_COLLATERAL_SWAP,
        "2026-04-10T09:00:00.000Z",
        "erc20",
        COW_SETTLEMENT,
        WALLET,
        "68",
        A_USDC,
        3,
    ),
    _transfer(
        AAVE_REPAY_WITH_COLLATERAL,
        "2026-04-11T09:00:00.000Z",
        "erc20",
        WALLET,
        REPAY_ADAPTER,
        "0.0011",
        A_CBBTC,
        1,
    ),
    _transfer(
        AAVE_REPAY_WITH_COLLATERAL,
        "2026-04-11T09:00:00.000Z",
        "erc20",
        WALLET,
        NO_ADDRESS,
        "74.97",
        DEBT_USDC,
        2,
    ),
    _transfer(
        AAVE_REPAY_WITH_COLLATERAL,
        "2026-04-11T09:00:00.000Z",
        "erc20",
        REPAY_ADAPTER,
        WALLET,
        "0.0000025",
        CBBTC,
        3,
    ),
]

_USDC_RESERVE, _CBBTC_RESERVE = AAVE_RESERVES

# What the market's own events say each of these transactions did, as AaveApi
# reads them from the receipts. Borrowing rounds a unit above what the wallet got.
AAVE_CHANGES: dict[str, list[LendingChange]] = {
    AAVE_SUPPLY: [LendingChange(reserve=_CBBTC_RESERVE, supplied=Decimal("0.004"))],
    AAVE_BORROW: [LendingChange(reserve=_USDC_RESERVE, borrowed=Decimal("150.000001"))],
    AAVE_REPAY: [
        LendingChange(
            reserve=_USDC_RESERVE,
            borrowed=Decimal("-50"),
            interest_due=Decimal("0.02"),
        )
    ],
    AAVE_REPAY_MINTING_DEBT: [
        LendingChange(
            reserve=_USDC_RESERVE,
            borrowed=Decimal("-0.01"),
            interest_due=Decimal("0.015"),
        )
    ],
    AAVE_WITHDRAW: [LendingChange(reserve=_CBBTC_RESERVE, supplied=Decimal("-0.001"))],
    AAVE_COLLATERAL_SWAP: [
        LendingChange(
            reserve=_CBBTC_RESERVE,
            transferred=Decimal("-0.001"),
            interest_earned=Decimal("0.00000002"),
        ),
        LendingChange(reserve=_USDC_RESERVE, transferred=Decimal("68")),
    ],
    AAVE_REPAY_WITH_COLLATERAL: [
        LendingChange(reserve=_CBBTC_RESERVE, transferred=Decimal("-0.0011")),
        LendingChange(
            reserve=_USDC_RESERVE,
            borrowed=Decimal("-75"),
            interest_due=Decimal("0.03"),
        ),
    ],
}

RECEIPTS: dict[str, dict[str, Any]] = {
    receipt["transactionHash"]: receipt
    for receipt in [
        _receipt(APPROVAL, WALLET, 50_000, l1_fee=1_000),
        _receipt(VAULT_DEPOSIT, WALLET, 300_000, l1_fee=2_000),
        _receipt(SWAP, WALLET, 200_000),
        _receipt(POISON_FAKE_TOKEN, ATTACKER, 60_000),
        _receipt(POISON_ZERO_VALUE, ATTACKER, 60_000),
        _receipt(FAILED, WALLET, 40_000, ok=False),
        _receipt(PAYMENT, WALLET, 60_000),
        _receipt(ETHEREUM_SEND_TO_COINBASE, WALLET, 21_000),
        _receipt(AAVE_SUPPLY, WALLET, 150_000),
        _receipt(AAVE_BORROW, WALLET, 250_000),
        _receipt(AAVE_REPAY, WALLET, 150_000),
        _receipt(AAVE_REPAY_MINTING_DEBT, WALLET, 150_000),
        _receipt(AAVE_WITHDRAW, WALLET, 150_000),
        _receipt(AAVE_COLLATERAL_SWAP, RELAYER, 400_000),
        _receipt(AAVE_REPAY_WITH_COLLATERAL, RELAYER, 600_000),
    ]
}
