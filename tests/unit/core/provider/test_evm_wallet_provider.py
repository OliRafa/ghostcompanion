from datetime import datetime, timezone
from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.entity.onchain_movement import OnChainMovement
from ghostcompanion.core.entity.token import DEFAULT_TOKENS, Token
from ghostcompanion.core.entity.wallet import Network, Wallet
from ghostcompanion.core.provider.evm_wallet import EvmWalletProvider
from ghostcompanion.infra.market_prices.market_price_adapter import MarketPriceAdapter
from tests.infra.evm_chain_api import InMemoryEvmChainApi
from tests.infra.yahoo_finance_api import InMemoryYahooFinanceApi
from tests.resources.evm.transfers import (
    APPROVAL,
    BRIDGE_PAYOUT,
    CBBTC,
    COINBASE_ETH_DEPOSIT,
    COINBASE_USDC_DEPOSIT,
    ETHEREUM_SEND_TO_COINBASE,
    FAILED,
    MERCHANT,
    PAYMENT,
    POISON_DUST,
    POISON_FAKE_TOKEN,
    POISON_ZERO_VALUE,
    SPAM_AIRDROP,
    SWAP,
    VAULT_DEPOSIT,
    VAULT_SHARE,
    WALLET,
)

TOKENS = list(DEFAULT_TOKENS) + [
    Token(
        network=Network.BASE,
        contract=CBBTC,
        symbol="CBBTC",
        data_source="GHOSTFOLIO",
        price_symbol="BTC",
    ),
    Token(
        network=Network.BASE,
        contract=VAULT_SHARE,
        symbol="ABTC",
        data_source="GHOSTFOLIO",
    ),
]


def transaction_id(transaction_hash: str) -> str:
    return transaction_hash.removeprefix("0x")


class EvmWalletProviderFactory:
    @fixture(autouse=True)
    def initialize_provider(self):
        self.wallet = Wallet(
            name="DeFi Wallet", networks=("ethereum", "base"), addresses=(WALLET,)
        )
        self.api = InMemoryEvmChainApi()
        self.provider = EvmWalletProvider(
            self.api, MarketPriceAdapter(InMemoryYahooFinanceApi())
        )
        self.movements = self.provider.get_movements(self.wallet, TOKENS)

    def of(self, transaction_hash: str) -> dict[str, OnChainMovement]:
        return {
            movement.symbol: movement
            for movement in self.movements
            if movement.transaction_id == transaction_id(transaction_hash)
        }


class TestTrackedTokens(EvmWalletProviderFactory):
    def should_credit_what_the_wallet_received(self):
        [usdc] = self.of(COINBASE_USDC_DEPOSIT).values()

        assert (usdc.symbol, usdc.quantity, usdc.fee) == ("USDC", Decimal("1000"), 0)
        assert usdc.account == "DeFi Wallet"
        assert usdc.executed_at == datetime(2026, 4, 2, 18, 23, tzinfo=timezone.utc)

    def should_count_native_coin_paid_by_a_contract(self):
        [eth] = self.of(BRIDGE_PAYOUT).values()

        assert (eth.symbol, eth.quantity) == ("ETH", Decimal("0.001"))

    def should_ignore_lookalike_and_spam_tokens(self):
        assert self.of(POISON_FAKE_TOKEN) == {}
        assert self.of(SPAM_AIRDROP) == {}

    def should_ignore_zero_value_transfers_made_in_the_wallets_name(self):
        assert self.of(POISON_ZERO_VALUE) == {}

    def should_still_count_real_dust_sent_to_the_wallet(self):
        [usdc] = self.of(POISON_DUST).values()

        assert usdc.quantity == Decimal("0.000011")

    def should_keep_the_data_source_of_each_token(self):
        movements = self.of(SWAP)

        assert movements["USDC"].data_source == "YAHOO"
        assert movements["CBBTC"].data_source == "GHOSTFOLIO"


class TestSwaps(EvmWalletProviderFactory):
    def should_give_both_sides_of_a_swap_the_same_transaction(self):
        movements = self.of(SWAP)

        assert movements["USDC"].quantity == Decimal("-340")
        assert movements["CBBTC"].quantity == Decimal("0.005")

    def when_token_has_no_price_should_leave_it_to_the_swap(self):
        movements = self.of(VAULT_DEPOSIT)

        assert movements["ABTC"].quantity == Decimal("480")
        assert movements["ABTC"].market_unit_price is None
        assert movements["USDC"].quantity == Decimal("-500")


class TestPrices(EvmWalletProviderFactory):
    def should_price_each_token_with_its_price_coin(self):
        movements = self.of(SWAP)

        # Latest closes before 2026-04-02.
        assert movements["USDC"].market_unit_price == Decimal("0.9998")
        assert movements["CBBTC"].market_unit_price == Decimal("68000.0")


class TestFees(EvmWalletProviderFactory):
    def should_charge_the_fee_with_the_l1_data_fee_in_eth(self):
        [eth] = self.of(APPROVAL).values()

        # 50_000 gas at 1 gwei plus 1_000 wei of L1 data fee.
        assert (eth.symbol, eth.quantity, eth.fee) == (
            "ETH",
            Decimal("0"),
            Decimal("0.000050000000001"),
        )

    def should_charge_the_fee_alongside_the_tokens_moved(self):
        movements = self.of(VAULT_DEPOSIT)

        assert movements["ETH"].fee == Decimal("0.000300000000002")
        assert movements["USDC"].fee == Decimal("0")

    def when_someone_else_signed_should_not_charge_the_wallet(self):
        assert self.of(POISON_ZERO_VALUE) == {}

    def when_transaction_failed_should_only_charge_the_fee(self):
        movements = self.of(FAILED)

        assert list(movements) == ["ETH"]
        assert movements["ETH"].fee == Decimal("0.00004")

    def when_wallet_did_not_send_should_ask_for_no_receipt(self):
        assert transaction_id(COINBASE_ETH_DEPOSIT) not in [
            transaction_id(x) for x in self.api.receipt_requests
        ]


class TestSends(EvmWalletProviderFactory):
    def should_keep_the_destination_address(self):
        movements = self.of(PAYMENT)

        assert movements["USDC"].quantity == Decimal("-60")
        assert movements["USDC"].destination_address == MERCHANT


class TestNetworks(EvmWalletProviderFactory):
    def should_read_every_network_the_wallet_spans(self):
        [eth] = self.of(ETHEREUM_SEND_TO_COINBASE).values()

        assert (eth.quantity, eth.fee) == (Decimal("-0.06"), Decimal("0.000021"))

    def should_drop_the_0x_prefix_from_transaction_ids(self):
        assert all(not x.transaction_id.startswith("0x") for x in self.movements)

    def should_return_movements_oldest_first(self):
        times = [movement.executed_at for movement in self.movements]

        assert times == sorted(times)
