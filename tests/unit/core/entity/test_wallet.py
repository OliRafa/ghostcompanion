from pydantic import ValidationError
from pytest import raises

from ghostcompanion.core.entity.wallet import Network, Wallet

BECH32_ADDRESS = "bc1qexampleaddressaaaaaaaaaaaaaaaaaaaaaaaa"
BASE58_ADDRESS = "1ExampLeLegacyAddressxxxxxxxxxxxxx"
EVM_ADDRESS = "0xAbCdEf0123456789aBcDeF0123456789AbCdEf01"


def build_wallet(*addresses: str) -> Wallet:
    return Wallet(name="Cold Storage", network=Network.BITCOIN, addresses=addresses)


class TestOwns:
    def should_own_its_addresses(self):
        wallet = build_wallet(BECH32_ADDRESS)

        assert wallet.owns(BECH32_ADDRESS) is True

    def should_not_own_other_addresses(self):
        wallet = build_wallet(BECH32_ADDRESS)

        assert wallet.owns(BASE58_ADDRESS) is False

    def when_address_is_bech32_should_ignore_case(self):
        wallet = build_wallet(BECH32_ADDRESS.upper())

        assert wallet.owns(BECH32_ADDRESS) is True

    def when_address_is_base58_should_respect_case(self):
        wallet = build_wallet(BASE58_ADDRESS)

        assert wallet.owns(BASE58_ADDRESS.lower()) is False

    def should_ignore_surrounding_whitespace(self):
        wallet = build_wallet(f" {BECH32_ADDRESS} ")

        assert wallet.owns(BECH32_ADDRESS) is True


class TestNativeSymbol:
    def when_network_is_bitcoin_should_be_btc(self):
        assert Network.BITCOIN.native_symbol == "BTC"

    def when_network_is_evm_should_be_eth(self):
        assert Network.ETHEREUM.native_symbol == Network.BASE.native_symbol == "ETH"


class TestNetworks:
    def when_given_one_network_should_hold_it_as_the_only_one(self):
        assert build_wallet(BECH32_ADDRESS).networks == (Network.BITCOIN,)

    def should_span_several_evm_networks(self):
        wallet = Wallet(
            name="DeFi", networks=("ethereum", "base"), addresses=(EVM_ADDRESS,)
        )

        assert wallet.networks == (Network.ETHEREUM, Network.BASE)
        assert wallet.is_evm is True

    def when_bitcoin_is_mixed_with_other_networks_should_raise_exception(self):
        with raises(ValidationError, match="bitcoin"):
            Wallet(name="Mixed", networks=("bitcoin", "base"), addresses=("x",))

    def when_both_network_keys_are_given_should_raise_exception(self):
        with raises(ValidationError, match="either"):
            Wallet(
                name="Both",
                network="base",
                networks=("base",),
                addresses=(EVM_ADDRESS,),
            )

    def when_evm_address_differs_in_case_should_still_own_it(self):
        wallet = Wallet(name="DeFi", network="base", addresses=(EVM_ADDRESS,))

        assert wallet.owns(EVM_ADDRESS.lower()) is True
        assert wallet.owns(EVM_ADDRESS.upper().replace("0X", "0x")) is True
