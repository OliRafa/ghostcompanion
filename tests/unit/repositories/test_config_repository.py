from pathlib import Path

from pytest import fixture, raises

from ghostcompanion.core.entity.token import WELL_KNOWN_CONTRACTS
from ghostcompanion.core.entity.wallet import Network, Wallet
from ghostcompanion.repositories.config import ConfigRepository, InvalidConfigException

ADDRESS_A = "bc1qexampleaddressaaaaaaaaaaaaaaaaaaaaaaaa"
ADDRESS_B = "bc1qexampleaddressbbbbbbbbbbbbbbbbbbbbbbbb"


class ConfigRepositoryFactory:
    @fixture(autouse=True)
    def initialize_config_path(self, tmp_path: Path):
        self.config_path = tmp_path.joinpath("ghostcompanion.yaml")

    def repository_with(self, content: str) -> ConfigRepository:
        self.config_path.write_text(content)
        return ConfigRepository(self.config_path)


class TestGetSymbolMappings(ConfigRepositoryFactory):
    def should_return_symbol_mappings(self):
        repository = self.repository_with("symbol_mapping:\n  EURN: CMBT\n")

        mappings = repository.get_symbol_mappings()

        assert [(change.old_symbol, change.new_symbol) for change in mappings] == [
            ("EURN", "CMBT")
        ]

    def when_file_is_missing_should_return_no_mappings(self):
        repository = ConfigRepository(self.config_path)

        assert repository.get_symbol_mappings() == []

    def when_file_is_empty_should_return_no_mappings(self):
        repository = self.repository_with("")

        assert repository.get_symbol_mappings() == []

    def when_only_legacy_file_exists_should_raise_exception(self):
        self.config_path.parent.joinpath("symbol_mapping.yaml").write_text("A: B\n")
        repository = ConfigRepository(self.config_path)

        with raises(InvalidConfigException, match="no longer read"):
            repository.get_symbol_mappings()


class TestGetWallets(ConfigRepositoryFactory):
    def should_return_wallets(self):
        repository = self.repository_with(
            f"""
wallets:
  - name: Cold Storage
    network: bitcoin
    addresses: [{ADDRESS_A}, {ADDRESS_B}]
"""
        )

        assert repository.get_wallets() == [
            Wallet(
                name="Cold Storage",
                network=Network.BITCOIN,
                addresses=(ADDRESS_A, ADDRESS_B),
            )
        ]

    def when_wallets_are_absent_should_return_no_wallets(self):
        repository = self.repository_with("symbol_mapping:\n  EURN: CMBT\n")

        assert repository.get_wallets() == []

    def when_network_is_unsupported_should_raise_exception(self):
        repository = self.repository_with(
            f"wallets:\n  - name: A\n    network: dogecoin\n"
            f"    addresses: [{ADDRESS_A}]\n"
        )

        with raises(InvalidConfigException):
            repository.get_wallets()

    def when_wallet_has_no_addresses_should_raise_exception(self):
        repository = self.repository_with(
            "wallets:\n  - name: A\n    network: bitcoin\n    addresses: []\n"
        )

        with raises(InvalidConfigException):
            repository.get_wallets()

    def when_wallet_names_repeat_should_raise_exception(self):
        repository = self.repository_with(
            f"""
wallets:
  - name: Cold Storage
    network: bitcoin
    addresses: [{ADDRESS_A}]
  - name: cold storage
    network: bitcoin
    addresses: [{ADDRESS_B}]
"""
        )

        with raises(InvalidConfigException, match="unique"):
            repository.get_wallets()

    def when_wallet_name_matches_a_broker_account_should_raise_exception(self):
        repository = self.repository_with(
            f"wallets:\n  - name: Coinbase\n    network: bitcoin\n"
            f"    addresses: [{ADDRESS_A}]\n"
        )

        with raises(InvalidConfigException, match="reserved"):
            repository.get_wallets()

    def when_wallet_name_matches_binance_should_raise_exception(self):
        repository = self.repository_with(
            f"wallets:\n  - name: binance\n    network: bitcoin\n"
            f"    addresses: [{ADDRESS_A}]\n"
        )

        with raises(InvalidConfigException, match="reserved"):
            repository.get_wallets()

    def when_address_is_in_two_wallets_should_raise_exception(self):
        repository = self.repository_with(
            f"""
wallets:
  - name: A
    network: bitcoin
    addresses: [{ADDRESS_A}]
  - name: B
    network: bitcoin
    addresses: [{ADDRESS_A.upper()}]
"""
        )

        with raises(InvalidConfigException, match="single wallet"):
            repository.get_wallets()


class TestGetTokens(ConfigRepositoryFactory):
    def tokens(self, content: str = "") -> dict:
        repository = self.repository_with(content)
        return {
            (token.network, token.contract): token for token in repository.get_tokens()
        }

    def when_none_are_configured_should_track_usdc_and_eth(self):
        tokens = self.tokens()

        usdc = tokens[(Network.BASE, WELL_KNOWN_CONTRACTS["USDC"][Network.BASE])]
        eth = tokens[(Network.ETHEREUM, None)]
        assert (usdc.symbol, usdc.data_source, usdc.price_symbol) == (
            "USDC",
            "YAHOO",
            "USDC",
        )
        assert (eth.symbol, eth.price_symbol) == ("ETH", "ETH")

    def when_token_is_well_known_should_track_it_on_every_network(self):
        tokens = self.tokens(
            "tokens:\n  cbBTC:\n    symbol: CBBTC\n    data_source: GHOSTFOLIO\n"
            "    price: BTC\n"
        )

        for network, contract in WELL_KNOWN_CONTRACTS["cbBTC"].items():
            token = tokens[(network, contract)]
            assert (token.symbol, token.data_source, token.price_symbol) == (
                "CBBTC",
                "GHOSTFOLIO",
                "BTC",
            )

    def when_token_is_unlisted_should_use_its_network_and_contract(self):
        tokens = self.tokens(
            "tokens:\n  ABTC:\n    network: base\n"
            "    contract: '0x3764f07752384450576c6d8b027d06ffa29e5ae9'\n"
            "    data_source: GHOSTFOLIO\n"
        )

        token = tokens[(Network.BASE, "0x3764f07752384450576c6d8b027d06ffa29e5ae9")]
        assert (token.symbol, token.data_source, token.price_symbol) == (
            "ABTC",
            "GHOSTFOLIO",
            None,
        )

    def when_a_default_is_configured_should_override_it(self):
        tokens = self.tokens("tokens:\n  USDC:\n    symbol: USDC-X\n")

        usdc = tokens[(Network.BASE, WELL_KNOWN_CONTRACTS["USDC"][Network.BASE])]
        assert usdc.symbol == "USDC-X"

    def when_unlisted_token_lacks_its_contract_should_raise_exception(self):
        repository = self.repository_with("tokens:\n  ABTC:\n    network: base\n")

        with raises(InvalidConfigException, match="needs both"):
            repository.get_tokens()

    def when_token_is_unknown_should_raise_exception(self):
        repository = self.repository_with("tokens:\n  ABTC:\n    symbol: ABTC\n")

        with raises(InvalidConfigException, match="well-known"):
            repository.get_tokens()

    def when_two_tokens_share_a_contract_should_raise_exception(self):
        repository = self.repository_with(
            "tokens:\n  cbBTC:\n    symbol: CBBTC\n  OTHER:\n    network: base\n"
            "    contract: '0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf'\n"
        )

        with raises(InvalidConfigException, match="same contract"):
            repository.get_tokens()

    def when_token_is_on_bitcoin_should_raise_exception(self):
        repository = self.repository_with(
            "tokens:\n  X:\n    network: bitcoin\n"
            "    contract: '0x3764f07752384450576c6d8b027d06ffa29e5ae9'\n"
        )

        with raises(InvalidConfigException, match="EVM"):
            repository.get_tokens()


class TestGetBinanceHistoryPath(ConfigRepositoryFactory):
    def should_resolve_a_relative_path_against_the_config_file(self):
        repository = self.repository_with("binance:\n  history_path: exports\n")

        assert (
            repository.get_binance_history_path()
            == self.config_path.parent.joinpath("exports")
        )

    def should_keep_an_absolute_path(self):
        repository = self.repository_with("binance:\n  history_path: /data/binance\n")

        assert repository.get_binance_history_path() == Path("/data/binance")

    def when_not_configured_should_return_none(self):
        repository = self.repository_with("symbol_mapping:\n  EURN: CMBT\n")

        assert repository.get_binance_history_path() is None

    def when_key_is_unknown_should_raise_exception(self):
        repository = self.repository_with("binance:\n  history: exports\n")

        with raises(InvalidConfigException):
            repository.get_binance_history_path()


class TestInvalidConfig(ConfigRepositoryFactory):
    def when_key_is_unknown_should_raise_exception(self):
        repository = self.repository_with("symbol_mappings:\n  EURN: CMBT\n")

        with raises(InvalidConfigException):
            repository.get_symbol_mappings()

    def when_yaml_is_malformed_should_raise_exception(self):
        repository = self.repository_with("symbol_mapping: [unclosed\n")

        with raises(InvalidConfigException):
            repository.get_symbol_mappings()
