from pydantic import ValidationError
from pytest import raises

from ghostcompanion.core.entity.token import DEFAULT_TOKENS, Token
from ghostcompanion.core.entity.wallet import Network

CONTRACT = "0x3764F07752384450576C6D8B027D06FFA29E5AE9"


class TestToken:
    def should_normalize_the_contract(self):
        token = Token(network=Network.BASE, contract=CONTRACT, symbol="ABTC")

        assert token.contract == CONTRACT.lower()

    def when_contract_is_malformed_should_raise_exception(self):
        with raises(ValidationError, match="contract"):
            Token(network=Network.BASE, contract="0x1234", symbol="ABTC")

    def should_accept_ghostfolio_data_sources_in_any_case(self):
        token = Token(network=Network.BASE, symbol="ABTC", data_source="ghostfolio")

        assert token.data_source == "GHOSTFOLIO"

    def when_data_source_is_unknown_should_raise_exception(self):
        with raises(ValidationError, match="data source"):
            Token(network=Network.BASE, symbol="ABTC", data_source="BINANCE")


class TestDefaultTokens:
    def should_track_usdc_and_eth_on_every_evm_network(self):
        tracked = {(token.network, token.symbol) for token in DEFAULT_TOKENS}

        assert tracked == {
            (network, symbol)
            for network in (Network.ETHEREUM, Network.BASE)
            for symbol in ("ETH", "USDC")
        }
