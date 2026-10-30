import logging
from functools import cached_property
from pathlib import Path
from typing import Self, final

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    PrivateAttr,
    ValidationError,
    model_validator,
)

from ghostcompanion.core.entity.symbol_change import SymbolChange
from ghostcompanion.core.entity.token import DEFAULT_TOKENS, WELL_KNOWN_CONTRACTS, Token
from ghostcompanion.core.entity.wallet import Network, Wallet

logger = logging.getLogger(__name__)

LEGACY_SYMBOL_MAPPING_FILE = "symbol_mapping.yaml"

# Accounts the importers create in Ghostfolio; a wallet sharing one of these names
# would have its activities mixed with the broker's.
_RESERVED_ACCOUNT_NAMES = {"binance", "coinbase", "interactive brokers", "tastytrade"}


class InvalidConfigException(Exception):
    ...


class _TokenEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Both are needed unless the token is a well-known one.
    network: Network | None = None
    contract: str | None = None
    symbol: str | None = None
    data_source: str = "YAHOO"
    price: str | None = None

    def resolve(self, name: str) -> list[Token]:
        if self.network or self.contract:
            if not (self.network and self.contract):
                raise ValueError(f"token `{name}` needs both `network` and `contract`")
            contracts = {self.network: self.contract}
        elif name in WELL_KNOWN_CONTRACTS:
            contracts = WELL_KNOWN_CONTRACTS[name]
        else:
            well_known = ", ".join(WELL_KNOWN_CONTRACTS)
            raise ValueError(
                f"token `{name}` isn't a well-known one ({well_known}):"
                " give its `network` and `contract`"
            )

        symbol = self.symbol or name
        price = self.price or (symbol if self.data_source.upper() == "YAHOO" else None)
        return [
            Token(
                network=network,
                contract=contract,
                symbol=symbol,
                data_source=self.data_source,
                price_symbol=price,
            )
            for network, contract in contracts.items()
        ]


class _BinanceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The folder of Transaction Records exports, which hold the trades the API
    # no longer returns.
    history_path: Path | None = None


class _ConfigFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binance: _BinanceEntry = _BinanceEntry()
    symbol_mapping: dict[str, str] = {}
    tokens: dict[str, _TokenEntry] = {}
    wallets: list[Wallet] = []

    _tokens: list[Token] = PrivateAttr(default_factory=list)

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

    @model_validator(mode="after")
    def _resolve_tokens(self) -> Self:
        configured: dict[tuple[Network, str | None], Token] = {}
        for name, entry in self.tokens.items():
            for token in entry.resolve(name):
                if not token.network.is_evm:
                    raise ValueError(f"token `{name}`: only EVM networks have tokens")
                key = (token.network, token.contract)
                if key in configured:
                    raise ValueError(
                        f"tokens `{configured[key].symbol}` and `{name}` are the same"
                        f" contract on {token.network.value}"
                    )
                configured[key] = token

        defaults = {(token.network, token.contract): token for token in DEFAULT_TOKENS}
        self._tokens = list({**defaults, **configured}.values())
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

    def get_binance_history_path(self) -> Path | None:
        """Where Binance's exports are, relative to the config file unless the
        path is absolute."""
        path = self._config.binance.history_path
        if path is None:
            return None
        return self.config_path.parent.joinpath(path.expanduser())

    def get_tokens(self) -> list[Token]:
        """The tokens EVM wallets track: USDC and each network's own coin, plus
        the ones configured, which can also override those two."""
        return self._config._tokens

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
