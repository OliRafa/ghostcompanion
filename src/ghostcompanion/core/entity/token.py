import re

from pydantic import BaseModel, ConfigDict, field_validator

from ghostcompanion.core.entity.wallet import Network

# Ghostfolio's DataSource enum.
DATA_SOURCES = {
    "ALPHA_VANTAGE",
    "COINGECKO",
    "EOD_HISTORICAL_DATA",
    "FINANCIAL_MODELING_PREP",
    "GHOSTFOLIO",
    "GOOGLE_SHEETS",
    "MANUAL",
    "RAPID_API",
    "YAHOO",
}

_CONTRACT = re.compile(r"^0x[0-9a-f]{40}$")


class Token(BaseModel):
    """A coin an EVM wallet holds on one network, and how Ghostfolio knows it.

    On-chain, only the contract identifies a token: names and symbols are free
    text, which address-poisoning scams exploit with lookalikes of real ones.
    """

    model_config = ConfigDict(frozen=True)

    network: Network
    # None for the network's own coin, which has no contract.
    contract: str | None = None
    symbol: str
    data_source: str = "YAHOO"
    # Yahoo coin pricing moves that aren't swaps; without one, the token is only
    # booked when a swap tells what it cost.
    price_symbol: str | None = None

    @field_validator("contract")
    @classmethod
    def _normalize_contract(cls, contract: str | None) -> str | None:
        if contract is None:
            return None
        contract = contract.strip().lower()
        if not _CONTRACT.match(contract):
            raise ValueError(f"`{contract}` is not a contract address")
        return contract

    @field_validator("data_source")
    @classmethod
    def _validate_data_source(cls, data_source: str) -> str:
        data_source = data_source.upper()
        if data_source not in DATA_SOURCES:
            raise ValueError(f"`{data_source}` is not a Ghostfolio data source")
        return data_source


WELL_KNOWN_CONTRACTS: dict[str, dict[Network, str]] = {
    "USDC": {
        Network.ETHEREUM: "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        Network.BASE: "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
    },
    "cbBTC": {
        Network.ETHEREUM: "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf",
        Network.BASE: "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf",
    },
}

DEFAULT_TOKENS: tuple[Token, ...] = tuple(
    [
        Token(network=network, symbol="ETH", price_symbol="ETH")
        for network in (Network.ETHEREUM, Network.BASE)
    ]
    + [
        Token(network=network, contract=contract, symbol="USDC", price_symbol="USDC")
        for network, contract in WELL_KNOWN_CONTRACTS["USDC"].items()
    ]
)
