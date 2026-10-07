import logging
from functools import cached_property
from pathlib import Path
from typing import Self, final

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from ghostcompanion.core.entity.symbol_change import SymbolChange
from ghostcompanion.core.entity.wallet import Wallet

logger = logging.getLogger(__name__)

LEGACY_SYMBOL_MAPPING_FILE = "symbol_mapping.yaml"

# Accounts the importers create in Ghostfolio; a wallet sharing one of these names
# would have its activities mixed with the broker's.
_RESERVED_ACCOUNT_NAMES = {"coinbase", "interactive brokers", "tastytrade"}


class InvalidConfigException(Exception):
    ...


class _ConfigFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol_mapping: dict[str, str] = {}
    wallets: list[Wallet] = []

    @model_validator(mode="after")
    def _validate_wallets(self) -> Self:
        names = [wallet.name.lower() for wallet in self.wallets]
        if len(names) != len(set(names)):
            raise ValueError("wallet names must be unique")

        reserved = _RESERVED_ACCOUNT_NAMES.intersection(names)
        if reserved:
            raise ValueError(f"wallet names {sorted(reserved)} are reserved")

        addresses = [address for wallet in self.wallets for address in wallet.addresses]
        if len(addresses) != len(set(addresses)):
            raise ValueError("an address can belong to a single wallet only")

        return self


@final
class ConfigRepository:
    def __init__(self, config_path: Path):
        self.config_path = config_path

    def get_symbol_mappings(self) -> list[SymbolChange]:
        return [
            SymbolChange(old_symbol=old_symbol, new_symbol=new_symbol)
            for old_symbol, new_symbol in self._config.symbol_mapping.items()
        ]

    def get_wallets(self) -> list[Wallet]:
        return self._config.wallets

    @cached_property
    def _config(self) -> _ConfigFile:
        if not self.config_path.exists():
            self._ensure_no_legacy_file()
            logger.info(f"No config file found at `{self.config_path}`, using defaults")
            return _ConfigFile()

        try:
            with self.config_path.open("r") as buffer:
                content = yaml.safe_load(buffer) or {}

            return _ConfigFile.model_validate(content)

        except (yaml.YAMLError, ValidationError) as error:
            raise InvalidConfigException(
                f"Invalid config file `{self.config_path}`: {error}"
            ) from error

    def _ensure_no_legacy_file(self):
        # Silently ignoring the old file would drop every mapping, and the next
        # export would then delete and re-create the mapped activities.
        legacy_file = self.config_path.parent.joinpath(LEGACY_SYMBOL_MAPPING_FILE)
        if legacy_file.exists():
            raise InvalidConfigException(
                f"`{legacy_file}` is no longer read. Move its mappings under the "
                f"`symbol_mapping` key of `{self.config_path}`."
            )
