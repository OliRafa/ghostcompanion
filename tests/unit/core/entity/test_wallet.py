from ghostcompanion.core.entity.wallet import Network, Wallet

BECH32_ADDRESS = "bc1qexampleaddressaaaaaaaaaaaaaaaaaaaaaaaa"
BASE58_ADDRESS = "1ExampLeLegacyAddressxxxxxxxxxxxxx"


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


class TestSymbol:
    def when_network_is_bitcoin_should_be_btc(self):
        assert build_wallet(BECH32_ADDRESS).symbol == "BTC"
