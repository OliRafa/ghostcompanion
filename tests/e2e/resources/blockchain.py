"""Deterministic on-chain source data for the wallet end-to-end tests: a Coinbase
withdrawal into the "Cold Storage" wallet and a payment from someone else."""

from typing import Any

from tests.e2e.resources.coinbase import TRANSACTIONS as COINBASE_TRANSACTIONS

COLD_STORAGE_ADDRESS = "bc1qe2ecoldstorage000000000000000000000000001"
WITHDRAWAL_TXID = "e1" * 32

COINBASE_WITHDRAWAL: dict[str, Any] = {
    "amount": {"amount": "-0.00101000", "currency": "BTC"},
    "created_at": "2020-07-01T12:00:00Z",
    "id": "5d0e9b1c-37a4-4f0e-8a51-6c2f4b9e7d13",
    "native_amount": {"amount": "-101.00", "currency": "USD"},
    "network": {
        "hash": WITHDRAWAL_TXID,
        "network_name": "bitcoin",
        "status": "pending",
        "transaction_fee": {"amount": "0.00001000", "currency": "BTC"},
    },
    "status": "completed",
    "to": {"address": COLD_STORAGE_ADDRESS, "resource": "address"},
    "type": "send",
}

COINBASE_TRANSACTIONS_WITH_WITHDRAWAL = COINBASE_TRANSACTIONS + [COINBASE_WITHDRAWAL]


def _status(block_time: int) -> dict[str, Any]:
    return {"confirmed": True, "block_height": 638000, "block_time": block_time}


BLOCKCHAIN_TRANSACTIONS: list[dict[str, Any]] = [
    {
        "txid": WITHDRAWAL_TXID,
        "status": _status(1593608400),  # 2020-07-01T13:00:00Z
        "fee": 5000,
        "vin": [
            {
                "prevout": {
                    "scriptpubkey_address": "bc1qe2ecoinbasehot0000000000000000000000",
                    "value": 1000000,
                }
            }
        ],
        "vout": [
            {"scriptpubkey_address": COLD_STORAGE_ADDRESS, "value": 100000},
            {
                "scriptpubkey_address": "bc1qe2ecoinbasechange00000000000000000000",
                "value": 895000,
            },
        ],
    },
    {
        "txid": "e2" * 32,
        "status": _status(1594382400),  # 2020-07-10T12:00:00Z
        "fee": 1000,
        "vin": [
            {
                "prevout": {
                    "scriptpubkey_address": "bc1qe2esender00000000000000000000000000",
                    "value": 300000,
                }
            }
        ],
        "vout": [
            {"scriptpubkey_address": COLD_STORAGE_ADDRESS, "value": 200000},
            {
                "scriptpubkey_address": "bc1qe2esenderchange000000000000000000000",
                "value": 99000,
            },
        ],
    },
]
