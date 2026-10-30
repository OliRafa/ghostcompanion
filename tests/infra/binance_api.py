from collections import defaultdict
from decimal import Decimal
from typing import Any

from ghostcompanion.core.ports.binance import BinancePort
from tests.resources.binance.api import (
    BALANCES,
    DEPOSITS,
    FIAT_DEPOSITS,
    FIAT_WITHDRAWALS,
    SYMBOLS,
    WITHDRAWALS,
)


class InMemoryBinanceApi(BinancePort):
    """The account behind `tests/resources/binance/transactions.csv`, unless
    given another. `scanned` lists the pairs whose trades were asked for."""

    def __init__(
        self,
        balances: dict[str, Decimal] | None = None,
        deposits: list[dict[str, Any]] | None = None,
        withdrawals: list[dict[str, Any]] | None = None,
        fiat_deposits: list[dict[str, Any]] | None = None,
        fiat_withdrawals: list[dict[str, Any]] | None = None,
        trades: dict[str, list[dict[str, Any]]] | None = None,
    ) -> None:
        self._balances = BALANCES if balances is None else balances
        self._deposits = DEPOSITS if deposits is None else deposits
        self._withdrawals = WITHDRAWALS if withdrawals is None else withdrawals
        self._fiat_deposits = FIAT_DEPOSITS if fiat_deposits is None else fiat_deposits
        self._fiat_withdrawals = (
            FIAT_WITHDRAWALS if fiat_withdrawals is None else fiat_withdrawals
        )
        self._trades = defaultdict(list, trades or {})
        self.scanned: list[str] = []

    def get_balances(self) -> dict[str, Decimal]:
        return dict(self._balances)

    def get_deposits(self) -> list[dict[str, Any]]:
        return self._deposits

    def get_withdrawals(self) -> list[dict[str, Any]]:
        return self._withdrawals

    def get_fiat_deposits(self) -> list[dict[str, Any]]:
        return self._fiat_deposits

    def get_fiat_withdrawals(self) -> list[dict[str, Any]]:
        return self._fiat_withdrawals

    def get_symbols(self) -> list[dict[str, Any]]:
        return SYMBOLS

    def get_trades(self, symbol: str) -> list[dict[str, Any]]:
        self.scanned.append(symbol)
        return self._trades[symbol]
