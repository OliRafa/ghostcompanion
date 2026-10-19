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
from tests.infra.yahoo_finance_api import InMemoryYahooFinanceApi
from tests.resources.evm.transfers import (
    CBBTC,
    COINBASE_USDC_DEPOSIT,
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
