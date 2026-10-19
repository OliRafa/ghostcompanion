from enum import Enum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Network(Enum):
    BITCOIN = "bitcoin"
    ETHEREUM = "ethereum"
    BASE = "base"

    @property
    def native_symbol(self) -> str:
        return _NATIVE_SYMBOLS[self]

    @property
    def is_evm(self) -> bool:
        return self is not Network.BITCOIN


_NATIVE_SYMBOLS = {Network.BITCOIN: "BTC", Network.ETHEREUM: "ETH", Network.BASE: "ETH"}

# Bech32 addresses are case-insensitive, while legacy base58 ones are not.
_BECH32_PREFIXES = ("bc1", "tb1", "bcrt1")


def normalize_address(address: str) -> str:
    address = address.strip()
    # EVM addresses are hex; their mixed case is only a checksum.
    if address.lower().startswith(_BECH32_PREFIXES + ("0x",)):
        return address.lower()

    return address


class Wallet(BaseModel):
    """A self-custody wallet, tracked as its own Ghostfolio account. An EVM wallet
    can span several networks, since the same address and keys work on all of
    them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    networks: tuple[Network, ...] = Field(min_length=1)
    addresses: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _accept_single_network(cls, data: Any) -> Any:
        if isinstance(data, dict) and "network" in data:
            if "networks" in data:
                raise ValueError("give either `network` or `networks`, not both")
            rest = {key: value for key, value in data.items() if key != "network"}
            data = {**rest, "networks": (data["network"],)}
        return data

    @field_validator("addresses")
    @classmethod
    def _normalize_addresses(cls, addresses: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(normalize_address(address) for address in addresses)

    @model_validator(mode="after")
    def _validate_networks(self) -> Self:
        if Network.BITCOIN in self.networks and len(self.networks) > 1:
            raise ValueError("a bitcoin wallet can't span other networks")
        if len(set(self.networks)) != len(self.networks):
            raise ValueError("networks must be unique")
        return self

    @property
    def is_evm(self) -> bool:
        return self.networks[0].is_evm

    def owns(self, address: str) -> bool:
        return normalize_address(address) in self.addresses
