"""Synthetic Binance API records matching `transactions.csv`: its crypto
deposits and withdrawals as the API lists them, with transaction ids, and the
balances its records add up to. The API already names NANO by its new name,
XNO, as Binance does for coins it renamed."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


def milliseconds(moment: str) -> int:
    return int(
        datetime.fromisoformat(moment).replace(tzinfo=timezone.utc).timestamp() * 1000
    )


LTC_DEPOSIT_HASH = "5f2c" + "1" * 60
XNO_DEPOSIT_HASH = "9C0D" + "2" * 60
XLM_WITHDRAWAL_HASH = "e71a" + "3" * 60

DEPOSITS: list[dict[str, Any]] = [
    {
        "id": "1001",
        "amount": "2.7183",
        "coin": "LTC",
        "network": "LTC",
        "status": 1,
        "address": "LExampleDepositAddressAAAAAAAAAAAAA",
        "txId": LTC_DEPOSIT_HASH,
        "insertTime": milliseconds("2019-02-03 09:11:02"),
        "transferType": 0,
    },
    {
        "id": "1002",
        "amount": "140",
        "coin": "XNO",
        "network": "NANO",
        "status": 1,
        "address": "nano_exampledepositaddress",
        "txId": XNO_DEPOSIT_HASH,
        "insertTime": milliseconds("2019-05-20 14:28:40"),
        "transferType": 0,
    },
    {
        "id": "1003",
        "amount": "0.5",
        "coin": "BTC",
        "network": "BTC",
        "status": 2,
        "address": "bc1qexampledepositaddress",
        "txId": "4" * 64,
        "insertTime": milliseconds("2020-01-10 10:00:00"),
        "transferType": 0,
    },
]

WITHDRAWALS: list[dict[str, Any]] = [
    {
        "id": "w-2001",
        "amount": "299.99",
        "transactionFee": "0.01",
        "coin": "XLM",
        "status": 6,
        "address": "GEXAMPLEWITHDRAWALADDRESS",
        "txId": XLM_WITHDRAWAL_HASH,
        "applyTime": "2021-07-22 08:04:51",
        "completeTime": "2021-07-22 08:09:10",
        "network": "XLM",
        "transferType": 0,
    },
    {
        "id": "w-2002",
        "amount": "0.01",
        "transactionFee": "0.0005",
        "coin": "BTC",
        "status": 1,
        "address": "bc1qexamplewithdrawaladdress",
        "txId": "",
        "applyTime": "2020-02-11 09:00:00",
        "network": "BTC",
        "transferType": 0,
    },
]

FIAT_DEPOSITS: list[dict[str, Any]] = [
    {
        "orderNo": "f-3001",
        "fiatCurrency": "BRL",
        "indicatedAmount": "2500.00",
        "amount": "2500.00",
        "totalFee": "0.00",
        "method": "Bank Transfer",
        "status": "Successful",
        "createTime": milliseconds("2021-03-09 11:14:30"),
        "updateTime": milliseconds("2021-03-09 11:20:00"),
    },
]

FIAT_WITHDRAWALS: list[dict[str, Any]] = [
    {
        "orderNo": "f-3002",
        "fiatCurrency": "EUR",
        "indicatedAmount": "487.25",
        "amount": "486.35",
        "totalFee": "0.90",
        "method": "Bank Account",
        "status": "Successful",
        "createTime": milliseconds("2021-04-20 07:50:00"),
        "updateTime": milliseconds("2021-04-20 07:55:40"),
    },
    {
        "orderNo": "f-3003",
        "fiatCurrency": "EUR",
        "indicatedAmount": "10.00",
        "amount": "9.10",
        "totalFee": "0.90",
        "method": "Bank Account",
        "status": "Successful",
        "createTime": milliseconds("2021-05-02 11:58:00"),
        "updateTime": milliseconds("2021-05-02 12:00:00"),
    },
]

BALANCES: dict[str, Decimal] = {
    "BRL": Decimal("925.37"),
    "BTC": Decimal("0.07373187"),
    "ETHW": Decimal("0.12345678"),
    "EUR": Decimal("14.60763"),
    "LTC": Decimal("0.2183"),
    "XLM": Decimal("10.1895"),
    "XNO": Decimal("40"),
    "XVG": Decimal("11988"),
}

SYMBOLS: list[dict[str, Any]] = [
    {"symbol": symbol, "baseAsset": base, "quoteAsset": quote, "status": status}
    for symbol, base, quote, status in (
        ("ADABTC", "ADA", "BTC", "TRADING"),
        ("BNBBTC", "BNB", "BTC", "TRADING"),
        ("BNBUSDT", "BNB", "USDT", "TRADING"),
        ("BTCBRL", "BTC", "BRL", "TRADING"),
        ("BTCEUR", "BTC", "EUR", "TRADING"),
        ("BTCUSDT", "BTC", "USDT", "TRADING"),
        ("ETHBTC", "ETH", "BTC", "TRADING"),
        ("LTCBTC", "LTC", "BTC", "TRADING"),
        ("NANOBTC", "NANO", "BTC", "BREAK"),
        ("XLMBTC", "XLM", "BTC", "TRADING"),
        ("XNOBTC", "XNO", "BTC", "TRADING"),
        ("XRPBTC", "XRP", "BTC", "BREAK"),
        ("XRPUSDT", "XRP", "USDT", "TRADING"),
        ("XVGBTC", "XVG", "BTC", "TRADING"),
    )
]

# Daily closes for the coins the records price: a deposit or withdrawal at its
# coin's close, a trade of a coin for another by its BTC side.
PRICE_HISTORIES: dict[str, tuple[str, dict[str, float]]] = {
    "BTC-USD": (
        "UTC",
        {
            "2019-02-01": 3480.0,
            "2019-06-01": 8550.0,
            "2020-08-01": 11320.0,
            "2021-07-01": 33540.0,
            "2023-03-01": 23650.0,
        },
    ),
    "LTC-USD": ("UTC", {"2019-02-01": 33.21}),
    "XLM-USD": ("UTC", {"2021-07-01": 0.2611}),
    "XNO-USD": ("UTC", {"2019-05-01": 1.327}),
}
