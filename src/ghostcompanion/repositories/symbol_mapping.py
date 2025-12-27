from pathlib import Path
from typing import final

import yaml

from ghostcompanion.core.entity.symbol_change import SymbolChange


class SymbolMappingsNotFoundException(Exception): ...


@final
class SymbolMappingRepository:
    def __init__(self):
        self.mapping_file_path = Path.cwd().joinpath("symbol_mapping.yaml")

    @staticmethod
    def _load_mapping_file(file_path: Path) -> dict[str, str]:
        with file_path.open("r") as buffer:
            return yaml.safe_load(buffer.read())

    def get_symbol_mappings(self) -> list[SymbolChange]:
        try:
            mappings = self._load_mapping_file(self.mapping_file_path)
            changes = []
            for old_symbol, new_symbol in mappings.items():
                changes.append(
                    SymbolChange(old_symbol=old_symbol, new_symbol=new_symbol)
                )

            return changes

        except FileNotFoundError:
            raise SymbolMappingsNotFoundException()
