from tastytrade_ghostfolio.core.entity.symbol_change import SymbolChange
from tastytrade_ghostfolio.repositories.symbol_mapping import (
    SymbolMappingsNotFoundException,
)


class InMemorySymbolMappingRepository:
    def __init__(self, symbol_changes: list[SymbolChange] | None = None) -> None:
        self._symbol_changes = symbol_changes

    def get_symbol_mappings(self) -> list[SymbolChange]:
        if self._symbol_changes is None:
            raise SymbolMappingsNotFoundException()

        return self._symbol_changes
