from abc import ABC, abstractmethod

from ghostcompanion.core.entity.split import Split
from ghostcompanion.core.entity.symbol_change import SymbolChange
from ghostcompanion.core.entity.trade import Trade


class TastytradePort(ABC):
    @abstractmethod
    def get_trades(self, asset: str | None = None) -> list[Trade]: ...

    @abstractmethod
    def get_assets(self) -> list[str]: ...

    @abstractmethod
    def get_symbol_changes(self) -> list[SymbolChange]: ...

    @abstractmethod
    def get_splits(self) -> list[Split]: ...

    @abstractmethod
    def get_dividends(self, asset: str | None = None) -> list[Trade]: ...
