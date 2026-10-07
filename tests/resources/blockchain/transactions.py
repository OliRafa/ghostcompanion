"""Synthetic Esplora transactions around the "Cold Storage" wallet.

Amounts are in satoshis and add up (inputs = outputs + fee), with each spend
consuming outputs created by earlier transactions."""

from typing import Any

COLD_STORAGE_ADDRESS_1 = "bc1qcoldstorage00000000000000000000000000001"
COLD_STORAGE_ADDRESS_2 = "bc1qcoldstorage00000000000000000000000000002"
COINBASE_HOT_ADDRESS = "bc1qcoinbasehot000000000000000000000000000000"
COINBASE_CHANGE_ADDRESS = "bc1qcoinbasechange0000000000000000000000000000"
OTHER_COINBASE_USER_ADDRESS = "bc1qothercoinbaseuser000000000000000000000000"
SENDER_ADDRESS = "bc1qsender000000000000000000000000000000000000"
SENDER_CHANGE_ADDRESS = "bc1qsenderchange0000000000000000000000000000"
MERCHANT_ADDRESS = "bc1qmerchant0000000000000000000000000000000000"
UNLISTED_ADDRESS = "bc1qunlisted0000000000000000000000000000000000"

# Coinbase batches withdrawals: one transaction pays many customers.
COINBASE_WITHDRAWAL_TXID = "a1" * 32
EXTERNAL_RECEIVE_TXID = "a2" * 32
EXTERNAL_SEND_TXID = "a3" * 32
CONSOLIDATION_TXID = "a4" * 32
MIXED_INPUTS_TXID = "a5" * 32
UNCONFIRMED_TXID = "a6" * 32


def _output(address: str, value: int) -> dict[str, Any]:
    return {"scriptpubkey_address": address, "value": value}


def _input(address: str, value: int) -> dict[str, Any]:
    return {"prevout": _output(address, value), "is_coinbase": False}


def _status(block_time: int) -> dict[str, Any]:
    return {"confirmed": True, "block_height": 800000, "block_time": block_time}


TRANSACTIONS: list[dict[str, Any]] = [
    {
        "txid": COINBASE_WITHDRAWAL_TXID,
        "status": _status(1709294400),  # 2024-03-01T12:00:00Z
        "fee": 7733,
        "vin": [_input(COINBASE_HOT_ADDRESS, 50000000)],
        "vout": [
            _output(COLD_STORAGE_ADDRESS_1, 723422),
            _output(OTHER_COINBASE_USER_ADDRESS, 10000000),
            _output(COINBASE_CHANGE_ADDRESS, 39268845),
        ],
    },
    {
        "txid": EXTERNAL_RECEIVE_TXID,
        "status": _status(1709640000),  # 2024-03-05T12:00:00Z
        "fee": 1000,
        "vin": [_input(SENDER_ADDRESS, 2000000)],
        "vout": [
            _output(COLD_STORAGE_ADDRESS_2, 1000000),
            _output(SENDER_CHANGE_ADDRESS, 999000),
        ],
    },
    {
        "txid": EXTERNAL_SEND_TXID,
        "status": _status(1717329600),  # 2024-06-02T12:00:00Z
        "fee": 3422,
        "vin": [_input(COLD_STORAGE_ADDRESS_1, 723422)],
        "vout": [
            _output(MERCHANT_ADDRESS, 500000),
            _output(COLD_STORAGE_ADDRESS_2, 220000),
        ],
    },
    {
        "txid": CONSOLIDATION_TXID,
        "status": _status(1718020800),  # 2024-06-10T12:00:00Z
        "fee": 2000,
        "vin": [
            _input(COLD_STORAGE_ADDRESS_2, 1000000),
            _input(COLD_STORAGE_ADDRESS_2, 220000),
        ],
        "vout": [_output(COLD_STORAGE_ADDRESS_1, 1218000)],
    },
    {
        "txid": MIXED_INPUTS_TXID,
        "status": _status(1718884800),  # 2024-06-20T12:00:00Z
        "fee": 10000,
        "vin": [
            _input(COLD_STORAGE_ADDRESS_1, 1218000),
            _input(UNLISTED_ADDRESS, 782000),
        ],
        "vout": [_output(MERCHANT_ADDRESS, 1990000)],
    },
    {
        "txid": UNCONFIRMED_TXID,
        "status": {"confirmed": False},
        "fee": 500,
        "vin": [_input(SENDER_ADDRESS, 999000)],
        "vout": [
            _output(COLD_STORAGE_ADDRESS_1, 300000),
            _output(SENDER_CHANGE_ADDRESS, 698500),
        ],
    },
]
