from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.entity.portfolio import Portfolio
from ghostcompanion.core.entity.symbol_change import SymbolChange
from ghostcompanion.core.entity.trade import Trade
from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.entity.wallet import Network, Wallet
from ghostcompanion.core.provider.blockchain import BlockchainProvider
from ghostcompanion.core.provider.coinbase import CoinbaseProvider
from ghostcompanion.core.usecase.export_portfolio import ExportPortfolio
from ghostcompanion.core.usecase.import_crypto_transactions import (
    ImportCryptoTransactions,
)
from ghostcompanion.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from ghostcompanion.infra.market_prices.market_price_adapter import MarketPriceAdapter
from tests.infra.blockchain_api import InMemoryBlockchainApi
from tests.infra.coinbase_api import InMemoryCoinbaseApi
from tests.infra.config_repository import InMemoryConfigRepository
from tests.infra.ghostfolio_api import InMemoryGhostfolioApi
from tests.infra.yahoo_finance_api import InMemoryYahooFinanceApi
from tests.resources.blockchain.transactions import (
    COLD_STORAGE_ADDRESS_1,
    COLD_STORAGE_ADDRESS_2,
    MERCHANT_ADDRESS,
)

COLD_STORAGE = Wallet(
    name="Cold Storage",
    network=Network.BITCOIN,
    addresses=(COLD_STORAGE_ADDRESS_1, COLD_STORAGE_ADDRESS_2),
)


class ImportCryptoTransactionsFactory:
    @fixture(autouse=True)
    def initialize_import_crypto_transactions(self):
        self.ghostfolio_api = InMemoryGhostfolioApi()
        self.ghostfolio = GhostfolioAdapter(self.ghostfolio_api)
        self.config_repository = InMemoryConfigRepository(wallets=[COLD_STORAGE])
        market_prices = MarketPriceAdapter(InMemoryYahooFinanceApi())
        self.import_crypto_transactions = ImportCryptoTransactions(
            BlockchainProvider(InMemoryBlockchainApi(), market_prices),
            CoinbaseProvider(InMemoryCoinbaseApi()),
            self.config_repository,
            self.ghostfolio,
        )

    def portfolio(self, account: str) -> Portfolio:
        portfolios = self.import_crypto_transactions.execute()
        return next(x for x in portfolios if x.account.name == account)

    @staticmethod
    def trades(portfolio: Portfolio, description: str) -> list[Trade]:
        return [
            x for x in portfolio.get_trades("BTCUSD") if x.description == description
        ]


class TestCoinbasePortfolio(ImportCryptoTransactionsFactory):
    def should_add_assets_to_portfolio(self):
        portfolio = self.portfolio("Coinbase")

        assert portfolio.get_symbols() is not None

    def should_use_yahoo_as_data_source(self):
        trades = self.portfolio("Coinbase").get_trades("BTCUSD")

        assert all(trade.data_source == "YAHOO" for trade in trades)

    def should_adapt_symbols_for_yahoo_data_source(self):
        assets = self.portfolio("Coinbase").get_symbols()

        assert assets == ["ETHUSD", "BTCUSD"]

    def should_treat_network_fees_as_sells_with_zero_gain(self):
        network_fees = self.trades(self.portfolio("Coinbase"), "Network Fee")

        assert [
            (x.transaction_type, x.quantity, x.unit_price) for x in network_fees
        ] == [
            (TransactionType.SELL, Decimal("0.03497583"), Decimal("0")),
            (TransactionType.SELL, Decimal("0.00001029"), Decimal("0")),
        ]

    def when_coin_has_0_network_fee_should_not_create_sells_for_it(self):
        trades = self.portfolio("Coinbase").get_trades("ETHUSD")

        assert all(
            trade.quantity > 0
            for trade in trades
            if trade.transaction_type == TransactionType.SELL
        )

    def should_take_into_account_symbol_maps(self):
        self.config_repository._symbol_changes = [
            SymbolChange(old_symbol="ETHUSD", new_symbol="NOTETH")
        ]

        portfolio = self.portfolio("Coinbase")

        assert portfolio.has_asset("NOTETH") is True


class TestWalletPortfolio(ImportCryptoTransactionsFactory):
    def should_create_an_account_per_wallet(self):
        portfolios = self.import_crypto_transactions.execute()

        assert [portfolio.account.name for portfolio in portfolios] == [
            "Coinbase",
            "Cold Storage",
        ]
        assert any(
            account["name"] == "Cold Storage"
            for account in self.ghostfolio_api.get_accounts()
        )

    def should_adapt_symbols_for_yahoo_data_source(self):
        assert self.portfolio("Cold Storage").get_symbols() == ["BTCUSD"]

    def should_buy_coins_received_from_others_at_market(self):
        received = self.trades(self.portfolio("Cold Storage"), "Received")

        assert [(x.quantity, x.unit_price) for x in received] == [
            (Decimal("0.01"), Decimal("61000"))
        ]

    def should_sell_coins_sent_to_others_at_market(self):
        portfolio = self.portfolio("Cold Storage")

        sent = self.trades(portfolio, f"Sent to {MERCHANT_ADDRESS}")
        assert [(x.quantity, x.unit_price) for x in sent] == [
            (Decimal("0.005"), Decimal("67000")),
            (Decimal("0.0121191"), Decimal("67000")),
        ]

    def should_sell_the_network_fees_it_paid(self):
        fees = self.trades(self.portfolio("Cold Storage"), "Network Fee")

        assert [x.quantity for x in fees] == [
            Decimal("0.00003422"),
            Decimal("0.00002"),
            Decimal("0.0000609"),
        ]


class TestCoinbaseToWalletTransfer(ImportCryptoTransactionsFactory):
    def should_move_what_the_wallet_received_at_coinbase_market_price(self):
        portfolios = self.import_crypto_transactions.execute()
        coinbase, cold_storage = portfolios

        [sent] = self.trades(coinbase, "Transfer to Cold Storage")
        [received] = self.trades(cold_storage, "Transfer from Coinbase")
        assert sent.transaction_type == TransactionType.SELL
        assert received.transaction_type == TransactionType.BUY
        assert sent.quantity == received.quantity == Decimal("0.00723422")
        assert sent.unit_price == received.unit_price
        assert sent.executed_at == received.executed_at
        # Coinbase's value for the withdrawal, rather than the day's close.
        assert received.unit_price == Decimal("441.92") / Decimal("0.00724451")

    def should_not_also_book_the_transfer_as_a_receipt(self):
        cold_storage = self.portfolio("Cold Storage")

        assert all(
            trade.quantity != Decimal("0.00723422")
            for trade in self.trades(cold_storage, "Received")
        )

    def when_coinbase_isnt_configured_should_buy_wallet_receipts_at_market(self):
        self.import_crypto_transactions.coinbase_provider = None

        portfolios = self.import_crypto_transactions.execute()

        [cold_storage] = portfolios
        received = self.trades(cold_storage, "Received")
        assert [(x.quantity, x.unit_price) for x in received] == [
            (Decimal("0.00723422"), Decimal("61000")),
            (Decimal("0.01"), Decimal("61000")),
        ]


class TestExport(ImportCryptoTransactionsFactory):
    def when_exported_twice_should_not_change_ghostfolio(self):
        export_portfolio = ExportPortfolio(self.ghostfolio)
        for portfolio in self.import_crypto_transactions.execute():
            export_portfolio.execute(portfolio)
        orders_after_first_export = list(self.ghostfolio_api._orders)

        for portfolio in self.import_crypto_transactions.execute():
            export_portfolio.execute(portfolio)

        assert self.ghostfolio_api._orders == orders_after_first_export
