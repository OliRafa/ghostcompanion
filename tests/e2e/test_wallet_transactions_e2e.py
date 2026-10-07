"""End-to-end: import a Coinbase withdrawal into a self-custody wallet, plus a
payment the wallet got from someone else, into a real Ghostfolio instance.

Coinbase valued the 0.00101 BTC withdrawal at $101, so the 0.001 BTC that reached
the wallet is sold by Coinbase and bought by the wallet at that market price,
100000/coin, whatever Coinbase paid for the coins.
"""

from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.entity.wallet import Network, Wallet
from ghostcompanion.core.provider.blockchain import BlockchainProvider
from ghostcompanion.core.provider.coinbase import CoinbaseProvider
from ghostcompanion.core.usecase.export_portfolio import ExportPortfolio
from ghostcompanion.core.usecase.import_crypto_transactions import (
    ImportCryptoTransactions,
)
from ghostcompanion.infra.market_prices.market_price_adapter import MarketPriceAdapter
from tests.e2e.resources.blockchain import (
    BLOCKCHAIN_TRANSACTIONS,
    COINBASE_TRANSACTIONS_WITH_WITHDRAWAL,
    COLD_STORAGE_ADDRESS,
)
from tests.e2e.resources.coinbase import InMemoryCoinbaseApi
from tests.infra.blockchain_api import InMemoryBlockchainApi
from tests.infra.config_repository import InMemoryConfigRepository
from tests.infra.yahoo_finance_api import InMemoryYahooFinanceApi

COLD_STORAGE = Wallet(
    name="Cold Storage", network=Network.BITCOIN, addresses=(COLD_STORAGE_ADDRESS,)
)


class WalletTransactionsE2E:
    @fixture(autouse=True)
    def imported_portfolios(self, ghostfolio):
        self.ghostfolio = ghostfolio
        self.import_and_export()

    def import_and_export(self):
        coinbase_api = InMemoryCoinbaseApi()
        coinbase_api._transactions = COINBASE_TRANSACTIONS_WITH_WITHDRAWAL
        market_prices = MarketPriceAdapter(InMemoryYahooFinanceApi())
        use_case = ImportCryptoTransactions(
            BlockchainProvider(
                InMemoryBlockchainApi(BLOCKCHAIN_TRANSACTIONS), market_prices
            ),
            CoinbaseProvider(coinbase_api),
            InMemoryConfigRepository(wallets=[COLD_STORAGE]),
            self.ghostfolio,
        )

        export_portfolio = ExportPortfolio(self.ghostfolio)
        self.portfolios = {x.account.name: x for x in use_case.execute()}
        for portfolio in self.portfolios.values():
            export_portfolio.execute(portfolio)

    def orders_for(self, account: str):
        account_id = self.portfolios[account].account.id
        return self.ghostfolio.get_orders_by_symbol(account_id, "BTCUSD")


class TestTransfer(WalletTransactionsE2E):
    def should_sell_coins_out_of_coinbase_at_the_market_price(self):
        orders = self.orders_for("Coinbase")

        sells = [
            (order.quantity, order.unit_price)
            for order in orders
            if order.transaction_type == TransactionType.SELL
        ]
        assert (Decimal("0.001"), Decimal("100000")) in sells
        # The network fee Coinbase charged on top of the withdrawal.
        assert (Decimal("0.00001"), Decimal("0")) in sells

    def should_buy_coins_into_the_wallet_at_the_same_price(self):
        orders = self.orders_for("Cold Storage")

        buys = [
            (order.quantity, order.unit_price)
            for order in orders
            if order.transaction_type == TransactionType.BUY
        ]
        assert (Decimal("0.001"), Decimal("100000")) in buys


class TestReceipt(WalletTransactionsE2E):
    def should_buy_coins_received_from_others_at_market(self):
        orders = self.orders_for("Cold Storage")

        # Latest synthetic BTC-USD close before 2020-07-10.
        assert [(x.quantity, x.unit_price) for x in orders] == [
            (Decimal("0.001"), Decimal("100000")),
            (Decimal("0.002"), Decimal("9500")),
        ]


class TestIdempotency(WalletTransactionsE2E):
    def when_imported_again_should_leave_activities_untouched(self):
        ids_before = {
            account: sorted(order.id for order in self.orders_for(account))
            for account in self.portfolios
        }

        self.import_and_export()

        ids_after = {
            account: sorted(order.id for order in self.orders_for(account))
            for account in self.portfolios
        }
        assert ids_after == ids_before
