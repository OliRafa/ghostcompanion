from datetime import datetime, timezone
from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.entity.lending import LendingChange
from ghostcompanion.core.entity.onchain_movement import OnChainMovement
from ghostcompanion.core.entity.token import DEFAULT_TOKENS, Token
from ghostcompanion.core.entity.wallet import Network, Wallet
from ghostcompanion.core.provider.evm_wallet import EvmWalletProvider
from ghostcompanion.infra.market_prices.market_price_adapter import MarketPriceAdapter
from tests.infra.defillama_api import InMemoryDefiLlamaApi
from tests.infra.evm_chain_api import InMemoryEvmChainApi
from tests.infra.lending_market_api import InMemoryLendingMarketApi
from tests.infra.yahoo_finance_api import InMemoryYahooFinanceApi
from tests.resources.evm.transfers import (
    AAVE_BORROW,
    AAVE_COLLATERAL_SWAP,
    AAVE_RELAYED_TRANSFERS,
    AAVE_REPAY,
    AAVE_REPAY_MINTING_DEBT,
    AAVE_REPAY_WITH_COLLATERAL,
    AAVE_RESERVES,
    AAVE_SUPPLY,
    AAVE_TRANSFERS,
    AAVE_WITHDRAW,
    APPROVAL,
    BASE_TRANSFERS,
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
    USDC_BASE,
    VAULT_DEPOSIT,
    VAULT_SHARE,
    WALLET,
)

AAVE = EvmWalletProvider.LENDING_MARKET

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

    def should_price_each_token_at_the_moment_of_its_transaction(self):
        provider = EvmWalletProvider(
            InMemoryEvmChainApi(),
            MarketPriceAdapter(InMemoryYahooFinanceApi(), InMemoryDefiLlamaApi()),
        )
        movements = provider.get_movements(self.wallet, TOKENS)
        price = {
            (movement.transaction_id, movement.symbol): movement.market_unit_price
            for movement in movements
        }

        assert price[(transaction_id(SWAP), "CBBTC")] == Decimal("68120.4")
        assert price[(transaction_id(COINBASE_USDC_DEPOSIT), "USDC")] == Decimal(
            "0.9997"
        )
        assert price[(transaction_id(COINBASE_ETH_DEPOSIT), "ETH")] == Decimal("2064.3")


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


class LendingFactory:
    @fixture(autouse=True)
    def initialize_provider(self):
        self.wallet = Wallet(name="DeFi Wallet", network="base", addresses=(WALLET,))
        self.lending_market = InMemoryLendingMarketApi()
        self.api = InMemoryEvmChainApi(
            {Network.BASE: BASE_TRANSFERS + AAVE_TRANSFERS + AAVE_RELAYED_TRANSFERS}
        )
        self.provider = EvmWalletProvider(
            self.api,
            MarketPriceAdapter(InMemoryYahooFinanceApi()),
            self.lending_market,
        )
        self.movements = self.provider.get_movements(self.wallet, TOKENS)

    def of(
        self, transaction_hash: str
    ) -> dict[tuple[str | None, str], OnChainMovement]:
        """The transaction's movements, by the market they happened in (None for
        the wallet's own coins) and coin."""
        return {
            (movement.market, movement.symbol): movement
            for movement in self.movements
            if movement.transaction_id == transaction_id(transaction_hash)
            and movement.symbol != "ETH"
            and not movement.interest
        }

    def interest_of(self, transaction_hash: str) -> dict[str, Decimal]:
        return {
            movement.symbol: movement.quantity
            for movement in self.movements
            if movement.transaction_id == transaction_id(transaction_hash)
            and movement.interest
        }


class TestLending(LendingFactory):
    def when_supplying_should_move_the_coin_into_the_market(self):
        movements = self.of(AAVE_SUPPLY)

        assert movements[(None, "CBBTC")].quantity == Decimal("-0.004")
        assert movements[(AAVE, "CBBTC")].quantity == Decimal("0.004")
        assert movements[(AAVE, "CBBTC")].data_source == "GHOSTFOLIO"
        assert movements[(None, "CBBTC")].destination_address is None

    def when_withdrawing_should_move_the_coin_out_of_the_market(self):
        movements = self.of(AAVE_WITHDRAW)

        assert movements[(None, "CBBTC")].quantity == Decimal("0.001")
        assert movements[(AAVE, "CBBTC")].quantity == Decimal("-0.001")

    def when_borrowing_should_owe_the_market_a_debt(self):
        movements = self.of(AAVE_BORROW)

        usdc = movements[(None, "USDC")]
        debt = movements[(AAVE, "DEBT-USDC")]
        assert (usdc.quantity, usdc.description) == (
            Decimal("150"),
            "Borrowed from Aave",
        )
        assert (debt.quantity, debt.description) == (
            Decimal("-150"),
            "Borrowed from Aave",
        )
        assert debt.data_source == "GHOSTFOLIO"
        assert debt.market_unit_price == usdc.market_unit_price == Decimal("0.9998")

    def when_repaying_should_pay_the_debt_with_what_was_sent(self):
        movements = self.of(AAVE_REPAY)

        usdc = movements[(None, "USDC")]
        debt = movements[(AAVE, "DEBT-USDC")]
        assert (usdc.quantity, usdc.description) == (Decimal("-50"), "Repaid to Aave")
        assert (debt.quantity, debt.description) == (Decimal("50"), "Repaid to Aave")
        assert usdc.destination_address is None

    def when_repaying_less_than_the_interest_due_should_still_be_a_repayment(self):
        movements = self.of(AAVE_REPAY_MINTING_DEBT)

        assert movements[(AAVE, "DEBT-USDC")].quantity == Decimal("0.01")
        assert movements[(AAVE, "DEBT-USDC")].description == "Repaid to Aave"

    def should_leave_plain_sends_to_others(self):
        movements = self.of(PAYMENT)

        assert list(movements) == [(None, "USDC")]
        assert movements[(None, "USDC")].destination_address == MERCHANT

    def should_ask_the_market_for_its_reserves_once_per_network(self):
        self.provider.get_movements(self.wallet, TOKENS)

        assert self.lending_market.reserve_requests == [Network.BASE]

    def should_book_the_markets_side_in_the_wallets_own_account(self):
        assert {x.account for x in self.movements} == {"DeFi Wallet"}
        assert {x.market for x in self.movements} == {None, AAVE}

    def should_mark_only_what_the_wallet_owes_as_a_debt(self):
        owed = {
            (x.symbol, x.market, x.interest): x.debt
            for x in self.movements
            if x.transaction_id
            in (transaction_id(AAVE_REPAY), transaction_id(AAVE_COLLATERAL_SWAP))
        }

        assert owed == {
            ("USDC", None, False): False,
            ("DEBT-USDC", AAVE, False): True,
            ("DEBT-USDC", AAVE, True): True,
            ("ETH", None, False): False,
            ("CBBTC", AAVE, False): False,
            ("CBBTC", AAVE, True): False,
            ("USDC", AAVE, False): False,
        }

    def should_take_what_the_wallet_got_as_the_principal(self):
        # The market's books put the debt a unit above the 150 the wallet got.
        movements = self.of(AAVE_BORROW)

        assert movements[(AAVE, "DEBT-USDC")].quantity == Decimal("-150")


class TestLendingRounding(LendingFactory):
    def added_for_nothing(self, transaction_hash: str) -> list[tuple]:
        return [
            (x.symbol, x.quantity, x.description)
            for x in self.movements
            if x.transaction_id == transaction_id(transaction_hash) and x.interest
        ]

    def when_the_market_rounds_a_new_debt_up_should_owe_the_unit_for_nothing(self):
        assert self.added_for_nothing(AAVE_BORROW) == [
            ("DEBT-USDC", Decimal("-0.000001"), "Rounded up by Aave")
        ]

    def when_the_market_rounds_a_repayment_should_book_the_difference(self):
        [usdc] = [x for x in AAVE_RESERVES if x.asset == USDC_BASE]
        self.lending_market = InMemoryLendingMarketApi(
            changes={
                AAVE_REPAY: [
                    LendingChange(reserve=usdc, borrowed=Decimal("-50.000001"))
                ]
            }
        )
        self.movements = EvmWalletProvider(
            self.api, MarketPriceAdapter(InMemoryYahooFinanceApi()), self.lending_market
        ).get_movements(self.wallet, TOKENS)

        assert self.of(AAVE_REPAY)[(AAVE, "DEBT-USDC")].quantity == Decimal("50")
        assert self.added_for_nothing(AAVE_REPAY) == [
            ("DEBT-USDC", Decimal("0.000001"), "Rounded down by Aave")
        ]

    def when_the_debt_moved_exactly_should_book_no_rounding(self):
        assert self.added_for_nothing(AAVE_REPAY) == [
            ("DEBT-USDC", Decimal("-0.02"), None)
        ]


class TestLendingInterest(LendingFactory):
    def should_book_interest_due_when_repaying(self):
        assert self.interest_of(AAVE_REPAY) == {"DEBT-USDC": Decimal("-0.02")}
        assert self.interest_of(AAVE_REPAY_MINTING_DEBT) == {
            "DEBT-USDC": Decimal("-0.015")
        }

    def should_book_interest_earned_on_the_coin_supplied(self):
        assert self.interest_of(AAVE_COLLATERAL_SWAP) == {
            "CBBTC": Decimal("0.00000002")
        }

    def should_book_interest_as_the_markets(self):
        assert {(x.account, x.market) for x in self.movements if x.interest} == {
            ("DeFi Wallet", AAVE)
        }

    def when_nothing_accrued_should_book_no_interest(self):
        assert self.interest_of(AAVE_SUPPLY) == {}


class TestRelayedLending(LendingFactory):
    def when_collateral_is_swapped_should_swap_it_inside_the_market(self):
        movements = self.of(AAVE_COLLATERAL_SWAP)

        assert movements == {
            (AAVE, "CBBTC"): movements[(AAVE, "CBBTC")],
            (AAVE, "USDC"): movements[(AAVE, "USDC")],
        }
        assert movements[(AAVE, "CBBTC")].quantity == Decimal("-0.001")
        assert movements[(AAVE, "USDC")].quantity == Decimal("68")

    def when_collateral_repays_a_debt_should_repay_it_from_the_market(self):
        movements = self.of(AAVE_REPAY_WITH_COLLATERAL)

        assert movements[(AAVE, "CBBTC")].quantity == Decimal("-0.0011")
        debt = movements[(AAVE, "DEBT-USDC")]
        assert (debt.quantity, debt.description) == (Decimal("75"), "Repaid to Aave")
        assert self.interest_of(AAVE_REPAY_WITH_COLLATERAL) == {
            "DEBT-USDC": Decimal("-0.03")
        }

    def should_credit_the_wallet_what_the_relayer_sent_back(self):
        leftover = self.of(AAVE_REPAY_WITH_COLLATERAL)[(None, "CBBTC")]

        assert (leftover.quantity, leftover.description) == (Decimal("0.0000025"), None)

    def should_read_the_receipts_the_wallet_did_not_sign(self):
        requested = [transaction_id(x) for x in self.api.receipt_requests]

        assert transaction_id(AAVE_COLLATERAL_SWAP) in requested
        assert transaction_id(AAVE_REPAY_WITH_COLLATERAL) in requested

    def when_someone_else_signed_should_not_charge_the_wallet(self):
        eth = [
            x
            for x in self.movements
            if x.transaction_id == transaction_id(AAVE_COLLATERAL_SWAP)
            and x.symbol == "ETH"
        ]

        assert eth == []


class TestWithoutLendingMarket(EvmWalletProviderFactory):
    def should_treat_moves_to_the_market_as_plain_sends(self):
        provider = EvmWalletProvider(
            InMemoryEvmChainApi({Network.BASE: AAVE_TRANSFERS}),
            MarketPriceAdapter(InMemoryYahooFinanceApi()),
        )
        wallet = Wallet(name="DeFi Wallet", network="base", addresses=(WALLET,))

        movements = provider.get_movements(wallet, TOKENS)

        assert {x.account for x in movements} == {"DeFi Wallet"}
        assert {x.market for x in movements} == {None}


class TestLendingBalances(LendingFactory):
    def balances(self) -> dict[str, tuple]:
        return {
            x.symbol: (x.account, x.market, x.quantity, x.data_source)
            for x in self.provider.get_lending_balances(self.wallet, TOKENS)
        }

    def should_read_what_was_supplied_and_what_is_owed(self):
        self.lending_market.set_position(WALLET, CBBTC, supplied="0.0031")
        self.lending_market.set_position(WALLET, USDC_BASE, borrowed="100.02")

        balances = self.balances()

        assert balances["CBBTC"] == (
            "DeFi Wallet",
            AAVE,
            Decimal("0.0031"),
            "GHOSTFOLIO",
        )
        assert balances["DEBT-USDC"] == (
            "DeFi Wallet",
            AAVE,
            Decimal("-100.02"),
            "GHOSTFOLIO",
        )

    def should_include_empty_positions(self):
        assert self.balances()["DEBT-CBBTC"][2] == Decimal("0")

    def when_there_is_no_lending_market_should_have_no_balances(self):
        provider = EvmWalletProvider(
            InMemoryEvmChainApi(), MarketPriceAdapter(InMemoryYahooFinanceApi())
        )

        assert provider.get_lending_balances(self.wallet, TOKENS) == []
