"""Deterministic in-memory source stubs for e2e tests.

The *source* side (Tastytrade, Yahoo) is stubbed so runs are repeatable and need
no secrets; only the *sink* (Ghostfolio) is real.
"""

from decimal import Decimal

import pandas as pd
from pandas import Timestamp
from tastytrade.account import Transaction

from ghostcompanion.core.ports.tastytrade import TastytradePort
from tests.e2e.resources.tastytrade import TRANSACTIONS


class InMemoryTastytradeApi(TastytradePort):
    def __init__(
        self,
        transactions: list[Transaction] = TRANSACTIONS,
        cash_balance: Decimal = Decimal("1234.56"),
    ) -> None:
        self._transactions = transactions
        self._cash_balance = cash_balance

    def get_trades_history(self) -> list[Transaction]:
        return self._transactions

    def get_current_cash_balance(self) -> Decimal:
        return self._cash_balance


class StubYahooFinanceApi:
    """Returns a per-share dividend price only for KO, empty for everything else."""

    def get_dividends_by_ticker(self, ticker: str) -> pd.Series:
        if ticker == "KO":
            return pd.Series(
                {Timestamp("2023-06-01 00:00:00-0400", tz="America/New_York"): 0.5}
            )
        return pd.Series([], dtype="float64")
