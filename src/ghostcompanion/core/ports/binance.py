from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any


class BinancePort(ABC):
    """Binance's API, which returns records as it names them (camelCase)."""

    @abstractmethod
    def get_balances(self) -> dict[str, Decimal]:
        """What the account holds of each coin now, Spot and Funding wallets
        together, locked amounts included."""
        ...

    @abstractmethod
    def get_deposits(self) -> list[dict[str, Any]]:
        """Every crypto deposit, whatever its status."""
        ...

    @abstractmethod
    def get_withdrawals(self) -> list[dict[str, Any]]:
        """Every crypto withdrawal, whatever its status."""
        ...

    @abstractmethod
    def get_fiat_deposits(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_fiat_withdrawals(self) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_symbols(self) -> list[dict[str, Any]]:
        """Every pair Binance has listed, delisted ones included."""
        ...

    @abstractmethod
    def get_trades(self, symbol: str) -> list[dict[str, Any]]:
        """The account's trades on `symbol` that the API still returns, which
        are none from before September 2022."""
        ...

    @abstractmethod
    def get_converts(self, since: datetime | None) -> list[dict[str, Any]]:
        """Every Convert order placed since `since`, or ever if None, whatever
        its status."""
        ...

    @abstractmethod
    def get_dust_conversions(self) -> list[dict[str, Any]]:
        """Each coin swept by the last 100 dust conversions, none from before
        December 2020: a record per coin, carrying its conversion's id."""
        ...
