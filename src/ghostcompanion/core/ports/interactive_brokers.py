from abc import ABC, abstractmethod

from ibflex import ChangeInDividendAccrual, Trade


class InteractiveBrokersPort(ABC):
    @abstractmethod
    def get_dividends_by_symbol(self, symbol: str) -> list[ChangeInDividendAccrual]: ...

    @abstractmethod
    def get_symbols(self) -> list[str]: ...

    @abstractmethod
    def get_trades_by_symbol(self, symbol: str) -> list[Trade]: ...
