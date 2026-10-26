from decimal import Decimal

from pytest import fixture, raises

from ghostcompanion.core.entity.portfolio import Portfolio
from ghostcompanion.core.entity.token import Token
from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.entity.wallet import Network, Wallet
from ghostcompanion.core.provider.blockchain import BlockchainProvider
from ghostcompanion.core.provider.coinbase import CoinbaseProvider
from ghostcompanion.core.provider.evm_wallet import EvmWalletProvider
from ghostcompanion.core.usecase.import_crypto_transactions import (
    ImportCryptoTransactions,
)
from ghostcompanion.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from ghostcompanion.infra.market_prices.market_price_adapter import MarketPriceAdapter
from tests.infra.blockchain_api import InMemoryBlockchainApi
from tests.infra.coinbase_api import InMemoryCoinbaseApi
from tests.infra.config_repository import InMemoryConfigRepository
from tests.infra.evm_chain_api import InMemoryEvmChainApi
from tests.infra.ghostfolio_api import InMemoryGhostfolioApi
from tests.infra.lending_market_api import InMemoryLendingMarketApi
from tests.infra.yahoo_finance_api import InMemoryYahooFinanceApi
from tests.resources.evm.transfers import (
    AAVE_RELAYED_TRANSFERS,
    AAVE_TRANSFERS,
    BASE_TRANSFERS,
    CBBTC,
    COINBASE_USDC_DEPOSIT,
    USDC_BASE,
    VAULT_SHARE,
    WALLET,
)

DEFI_WALLET = Wallet(
    name="DeFi Wallet", networks=("ethereum", "base"), addresses=(WALLET,)
)
TOKENS = [
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
USDC_ACCOUNT = {
    "id": "usdc-account",
    "type": "wallet",
    "balance": {"amount": "0", "currency": "USDC"},
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-04-02T18:23:00Z",
    "currency": {"code": "USDC", "type": "crypto"},
}
# Coinbase's side of the 1000 USDC deposit the wallet received on Base.
COINBASE_USDC_SEND = {
    "amount": {"amount": "-1000.000000", "currency": "USDC"},
    "created_at": "2026-04-02T18:20:00Z",
    "native_amount": {"amount": "-1000.10", "currency": "USD"},
    "network": {
        "hash": COINBASE_USDC_DEPOSIT,
        "network_name": "base",
        "transaction_fee": {"amount": "0.000000", "currency": "USDC"},
    },
    "status": "completed",
    "to": {"address": WALLET, "resource": "address"},
    "type": "send",
}


class ImportEvmWalletTransactionsFactory:
    @fixture(autouse=True)
    def initialize_use_case(self):
        market_prices = MarketPriceAdapter(InMemoryYahooFinanceApi())
        coinbase_api = InMemoryCoinbaseApi()
        coinbase_api._accounts = [USDC_ACCOUNT]
        coinbase_api._transactions = [COINBASE_USDC_SEND]
        self.import_crypto_transactions = ImportCryptoTransactions(
            BlockchainProvider(InMemoryBlockchainApi([]), market_prices),
            CoinbaseProvider(coinbase_api),
            InMemoryConfigRepository(wallets=[DEFI_WALLET], tokens=TOKENS),
            GhostfolioAdapter(InMemoryGhostfolioApi()),
            EvmWalletProvider(InMemoryEvmChainApi(), market_prices),
        )

    def portfolio(self, account: str) -> Portfolio:
        portfolios = self.import_crypto_transactions.execute()
        return next(x for x in portfolios if x.account.name == account)

    @staticmethod
    def summary(portfolio: Portfolio, symbol: str) -> list[tuple]:
        return [
            (x.transaction_type, x.quantity, x.data_source, x.description)
            for x in portfolio.get_trades(symbol)
        ]


class TestSymbols(ImportEvmWalletTransactionsFactory):
    def should_name_yahoo_coins_as_pairs_and_keep_other_symbols(self):
        symbols = self.portfolio("DeFi Wallet").get_symbols()

        assert sorted(symbols) == ["ABTC", "CBBTC", "ETHUSD", "USDCUSD"]

    def should_keep_the_data_source_of_each_coin(self):
        portfolio = self.portfolio("DeFi Wallet")

        assert {x.data_source for x in portfolio.get_trades("CBBTC")} == {"GHOSTFOLIO"}
        assert {x.data_source for x in portfolio.get_trades("USDCUSD")} == {"YAHOO"}


class TestTransfers(ImportEvmWalletTransactionsFactory):
    def should_pair_the_coinbase_withdrawal_with_the_wallet_deposit(self):
        portfolios = {
            x.account.name: x for x in self.import_crypto_transactions.execute()
        }

        [sent] = [
            x
            for x in portfolios["Coinbase"].get_trades("USDCUSD")
            if x.description == "Transfer to DeFi Wallet"
        ]
        [received] = [
            x
            for x in portfolios["DeFi Wallet"].get_trades("USDCUSD")
            if x.description == "Transfer from Coinbase"
        ]
        assert sent.quantity == received.quantity == Decimal("1000")
        assert sent.unit_price == received.unit_price == Decimal("1000.10") / 1000


class TestSwaps(ImportEvmWalletTransactionsFactory):
    def should_buy_vault_shares_at_what_the_wallet_paid(self):
        [deposit] = self.portfolio("DeFi Wallet").get_trades("ABTC")

        assert deposit.transaction_type == TransactionType.BUY
        assert deposit.description == "Swapped from USDC"
        # 500 USDC at 0.9998 for 480 shares.
        assert deposit.quantity == Decimal("480")
        assert deposit.unit_price == Decimal("499.9000") / Decimal("480")

    def should_book_the_cbbtc_bought_with_usdc(self):
        assert self.summary(self.portfolio("DeFi Wallet"), "CBBTC") == [
            (TransactionType.BUY, Decimal("0.005"), "GHOSTFOLIO", "Swapped from USDC")
        ]


class TestPoisoning(ImportEvmWalletTransactionsFactory):
    def should_book_nothing_for_lookalike_or_spoofed_transfers(self):
        usdc = self.portfolio("DeFi Wallet").get_trades("USDCUSD")

        # Only the real 0.000011 USDC dust, never the fake 340 or the 0-value spoof.
        received = [x.quantity for x in usdc if x.description == "Received"]
        assert received == [Decimal("0.000011")]


class TestMissingProvider:
    def when_evm_wallet_has_no_provider_should_raise_exception(self):
        market_prices = MarketPriceAdapter(InMemoryYahooFinanceApi())
        use_case = ImportCryptoTransactions(
            BlockchainProvider(InMemoryBlockchainApi([]), market_prices),
            None,
            InMemoryConfigRepository(wallets=[DEFI_WALLET]),
            GhostfolioAdapter(InMemoryGhostfolioApi()),
        )

        with raises(ValueError, match="ALCHEMY_API_KEY"):
            use_case.execute()


class ImportAaveFactory:
    transfers = BASE_TRANSFERS + AAVE_TRANSFERS

    @fixture(autouse=True)
    def initialize_use_case(self):
        market_prices = MarketPriceAdapter(InMemoryYahooFinanceApi())
        self.lending_market = InMemoryLendingMarketApi()
        self.ghostfolio_api = InMemoryGhostfolioApi()
        self.import_crypto_transactions = ImportCryptoTransactions(
            BlockchainProvider(InMemoryBlockchainApi([]), market_prices),
            None,
            InMemoryConfigRepository(wallets=[DEFI_WALLET], tokens=TOKENS),
            GhostfolioAdapter(self.ghostfolio_api),
            EvmWalletProvider(
                InMemoryEvmChainApi(
                    {Network.BASE: self.transfers, Network.ETHEREUM: []}
                ),
                market_prices,
                self.lending_market,
            ),
        )

    def portfolios(self) -> dict[str, Portfolio]:
        return {x.account.name: x for x in self.import_crypto_transactions.execute()}

    @staticmethod
    def holding(portfolio: Portfolio, symbol: str) -> Decimal:
        signs = {TransactionType.BUY: 1, TransactionType.SELL: -1}
        return sum(
            signs[x.transaction_type] * x.quantity
            for x in portfolio.get_trades(symbol)
            if x.transaction_type in signs
        )


class TestAave(ImportAaveFactory):
    @fixture(autouse=True)
    def set_positions(self, initialize_use_case):
        # 0.004 supplied and 0.001 withdrawn; 150 borrowed, which Aave rounded
        # up a unit, and 50.01 repaid, plus 0.035 due.
        self.lending_market.set_position(WALLET, CBBTC, supplied="0.003")
        self.lending_market.set_position(WALLET, USDC_BASE, borrowed="100.025001")

    def wallet(self) -> Portfolio:
        return self.portfolios()["DeFi Wallet"]

    def should_hold_what_the_market_holds_with_the_wallets_own_coins(self):
        self.lending_market.set_position(WALLET, CBBTC, supplied="0.0031")
        self.lending_market.set_position(WALLET, USDC_BASE, borrowed="100.030001")

        wallet = self.wallet()

        # 0.002 left in the wallet and 0.0031 in Aave.
        assert self.holding(wallet, "CBBTC") == Decimal("0.0051")
        assert self.holding(wallet, "DEBT-USDC") == Decimal("-100.030001")

    def should_book_interest_due_when_it_accrued(self):
        interest = [
            (x.executed_at.date().isoformat(), x.quantity)
            for x in self.wallet().get_trades("DEBT-USDC")
            if x.description == "Interest due to Aave"
        ]

        assert interest == [
            ("2026-04-08", Decimal("0.02")),
            ("2026-04-08", Decimal("0.015")),
        ]

    def should_buy_a_repaid_debt_back_for_nothing_with_what_repaid_it_as_fee(self):
        wallet = self.wallet()
        paid = [
            (x.quantity, x.quantity * x.unit_price)
            for x in wallet.get_trades("USDCUSD")
            if x.description == "Repaid to Aave"
        ]
        repaid = [
            (x.quantity, x.fee)
            for x in wallet.get_trades("DEBT-USDC")
            if x.description == "Repaid to Aave" and x.unit_price == 0
        ]

        assert len(repaid) == 2
        assert sorted(repaid) == sorted(paid)

    def should_owe_what_aave_rounded_up_for_nothing(self):
        rounded = [
            (x.transaction_type, x.quantity, x.unit_price)
            for x in self.wallet().get_trades("DEBT-USDC")
            if x.description == "Rounded up by Aave"
        ]

        assert rounded == [(TransactionType.SELL, Decimal("0.000001"), Decimal("0"))]

    def when_supplying_or_withdrawing_should_book_nothing(self):
        wallet = self.wallet()

        # 0.005 swapped for; supplying 0.004 and withdrawing 0.001 moved nothing.
        assert self.holding(wallet, "CBBTC") == Decimal("0.005")
        assert [x.description for x in wallet.get_trades("CBBTC")] == [
            "Swapped from USDC"
        ]

    def should_book_borrowed_coins_apart_from_received_ones(self):
        descriptions = [x.description for x in self.wallet().get_trades("USDCUSD")]

        assert descriptions.count("Borrowed from Aave") == 1
        assert descriptions.count("Repaid to Aave") == 2

    def should_owe_the_debt_with_the_same_descriptions(self):
        descriptions = [x.description for x in self.wallet().get_trades("DEBT-USDC")]

        assert descriptions.count("Borrowed from Aave") == 1
        assert descriptions.count("Repaid to Aave") == 2

    def should_keep_debts_under_their_own_symbol(self):
        debt = self.wallet().get_trades("DEBT-USDC")

        assert {x.data_source for x in debt} == {"GHOSTFOLIO"}

    def should_keep_everything_in_the_wallets_account(self):
        portfolios = self.portfolios()

        assert list(portfolios) == ["DeFi Wallet"]
        assert "Aave" not in [x["name"] for x in self.ghostfolio_api.get_accounts()]


class TestRelayedAave(ImportAaveFactory):
    transfers = BASE_TRANSFERS + AAVE_TRANSFERS + AAVE_RELAYED_TRANSFERS

    @fixture(autouse=True)
    def set_positions(self, initialize_use_case):
        # 0.004 supplied, 0.001 withdrawn, swapped and repaid with 0.001 and
        # 0.0011, plus 0.00000002 earned; 150 borrowed, which Aave rounded up a
        # unit, 50.01 repaid by the wallet and 75 with collateral, plus 0.065 due.
        self.lending_market.set_position(WALLET, CBBTC, supplied="0.00090002")
        self.lending_market.set_position(
            WALLET, USDC_BASE, supplied="68", borrowed="25.055001"
        )

    def booked(self, symbol: str) -> list[tuple]:
        wallet = self.portfolios()["DeFi Wallet"]
        return [(x.description, x.quantity) for x in wallet.get_trades(symbol)]

    def when_collateral_is_swapped_should_swap_it_on_aave(self):
        assert ("Swapped for USDC on Aave", Decimal("0.001")) in self.booked("CBBTC")
        assert ("Swapped from CBBTC on Aave", Decimal("68")) in self.booked("USDCUSD")

    def when_collateral_repays_a_debt_should_swap_only_what_aave_kept(self):
        cbbtc = self.booked("CBBTC")

        assert ("Swapped for DEBT-USDC on Aave", Decimal("0.0010975")) in cbbtc
        assert not [x for x in cbbtc if x[0].startswith("Transfer")]
        assert ("Swapped from CBBTC on Aave", Decimal("75")) in self.booked("DEBT-USDC")

    def when_balances_match_the_events_should_catch_up_nothing(self):
        wallet = self.portfolios()["DeFi Wallet"]

        # 0.0020025 in the wallet, the 0.0000025 Aave sent back included, and
        # 0.00090002 in Aave.
        assert self.holding(wallet, "CBBTC") == Decimal("0.00290252")
        assert self.holding(wallet, "DEBT-USDC") == Decimal("-25.055001")
        assert all(
            x.executed_at.year == 2026 and x.executed_at.month == 4
            for symbol in wallet.get_symbols()
            for x in wallet.get_trades(symbol)
        )
