from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Network(Enum):
    BITCOIN = "bitcoin"

    @property
    def symbol(self) -> str:
        return _NETWORK_SYMBOLS[self]


_NETWORK_SYMBOLS = {Network.BITCOIN: "BTC"}

# Bech32 addresses are case-insensitive, while legacy base58 ones are not.
_BECH32_PREFIXES = ("bc1", "tb1", "bcrt1")


def normalize_address(address: str) -> str:
    address = address.strip()
    if address.lower().startswith(_BECH32_PREFIXES):
        return address.lower()

    return address


class Wallet(BaseModel):
    """A self-custody wallet, tracked as its own Ghostfolio account."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    network: Network
    addresses: tuple[str, ...] = Field(min_length=1)

    @field_validator("addresses")
    @classmethod
    def _normalize_addresses(cls, addresses: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(normalize_address(address) for address in addresses)

    @property
    def symbol(self) -> str:
        return self.network.symbol

    def owns(self, address: str) -> bool:
        return normalize_address(address) in self.addresses
