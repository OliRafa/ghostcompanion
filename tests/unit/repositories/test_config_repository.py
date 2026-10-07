from pathlib import Path

from pytest import fixture, raises

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


class TestInvalidConfig(ConfigRepositoryFactory):
    def when_key_is_unknown_should_raise_exception(self):
        repository = self.repository_with("symbol_mappings:\n  EURN: CMBT\n")

        with raises(InvalidConfigException):
            repository.get_symbol_mappings()

    def when_yaml_is_malformed_should_raise_exception(self):
        repository = self.repository_with("symbol_mapping: [unclosed\n")

        with raises(InvalidConfigException):
            repository.get_symbol_mappings()
