"""End-to-end: import a Coinbase USDC withdrawal into an EVM wallet on Base, a swap
of that USDC for ETH and a payment out, into a real Ghostfolio instance.

Coinbase valued the 1000 USDC withdrawal at $1000, so it lands on both accounts at
$1. The swap sold 400 USDC at the day's 0.9998 close and bought 0.2 ETH with it:
1999.6/ETH, the price the swap got, not the day's ETH close.
"""

from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.entity.wallet import Network, Wallet
from ghostcompanion.core.provider.blockchain import BlockchainProvider
from ghostcompanion.core.provider.coinbase import CoinbaseProvider
from ghostcompanion.core.provider.evm_wallet import EvmWalletProvider
from ghostcompanion.core.usecase.export_portfolio import ExportPortfolio
from ghostcompanion.core.usecase.import_crypto_transactions import (
    ImportCryptoTransactions,
)
from ghostcompanion.infra.market_prices.market_price_adapter import MarketPriceAdapter
from tests.e2e.resources.coinbase import InMemoryCoinbaseApi
from tests.e2e.resources.evm import (
    COINBASE_TRANSACTIONS,
    MERCHANT,
    RECEIPTS,
    TRANSFERS,
    USDC_ACCOUNT,
    WALLET,
)
from tests.infra.blockchain_api import InMemoryBlockchainApi
from tests.infra.config_repository import InMemoryConfigRepository
from tests.infra.evm_chain_api import InMemoryEvmChainApi
from tests.infra.yahoo_finance_api import InMemoryYahooFinanceApi

DEFI_WALLET = Wallet(name="DeFi Wallet", network=Network.BASE, addresses=(WALLET,))


class EvmWalletTransactionsE2E:
    @fixture(autouse=True)
    def imported_portfolios(self, ghostfolio):
        self.ghostfolio = ghostfolio
        self.import_and_export()

    def import_and_export(self):
        coinbase_api = InMemoryCoinbaseApi()
        coinbase_api._accounts = [USDC_ACCOUNT]
        coinbase_api._transactions = COINBASE_TRANSACTIONS
        market_prices = MarketPriceAdapter(InMemoryYahooFinanceApi())
        use_case = ImportCryptoTransactions(
            BlockchainProvider(InMemoryBlockchainApi([]), market_prices),
            CoinbaseProvider(coinbase_api),
            InMemoryConfigRepository(wallets=[DEFI_WALLET]),
            self.ghostfolio,
            EvmWalletProvider(
                InMemoryEvmChainApi({Network.BASE: TRANSFERS}, RECEIPTS), market_prices
            ),
        )

        export_portfolio = ExportPortfolio(self.ghostfolio)
        self.portfolios = {x.account.name: x for x in use_case.execute()}
        for portfolio in self.portfolios.values():
            export_portfolio.execute(portfolio)

    def orders(self, account: str, symbol: str) -> list[tuple]:
        account_id = self.portfolios[account].account.id
        return sorted(
            (x.transaction_type.value, x.quantity, x.unit_price)
            for x in self.ghostfolio.get_orders_by_symbol(account_id, symbol)
        )


class TestTransfer(EvmWalletTransactionsE2E):
    def should_move_usdc_from_coinbase_into_the_wallet(self):
        assert self.orders("Coinbase", "USDCUSD") == [
            ("SELL", Decimal("1000"), Decimal("1"))
        ]
        assert ("BUY", Decimal("1000"), Decimal("1")) in self.orders(
            "DeFi Wallet", "USDCUSD"
        )


class TestSwap(EvmWalletTransactionsE2E):
    def should_sell_usdc_and_buy_eth_at_the_price_the_swap_got(self):
        assert ("SELL", Decimal("400"), Decimal("0.9998")) in self.orders(
            "DeFi Wallet", "USDCUSD"
        )
        assert ("BUY", Decimal("0.2"), Decimal("1999.6")) in self.orders(
            "DeFi Wallet", "ETHUSD"
        )

    def should_sell_the_network_fees_for_nothing(self):
        fees = [x for x in self.orders("DeFi Wallet", "ETHUSD") if x[0] == "SELL"]

        assert fees == [("SELL", Decimal("0.0001"), Decimal("0"))] * 2


class TestPayment(EvmWalletTransactionsE2E):
    def should_sell_usdc_paid_to_others_at_market(self):
        account_id = self.portfolios["DeFi Wallet"].account.id
        [payment] = [
            x
            for x in self.ghostfolio.get_orders_by_symbol(account_id, "USDCUSD")
            if x.description == f"Sent to {MERCHANT}"
        ]
        assert (payment.transaction_type, payment.quantity) == (
            TransactionType.SELL,
            Decimal("100"),
        )


class TestIdempotency(EvmWalletTransactionsE2E):
    def activity_ids(self) -> dict[tuple[str, str], list[str]]:
        return {
            (account, symbol): sorted(
                x.id
                for x in self.ghostfolio.get_orders_by_symbol(
                    portfolio.account.id, symbol
                )
            )
            for account, portfolio in self.portfolios.items()
            for symbol in ("USDCUSD", "ETHUSD")
        }

    def when_imported_again_should_leave_activities_untouched(self):
        ids_before = self.activity_ids()

        self.import_and_export()

        assert self.activity_ids() == ids_before
        assert len(ids_before[("DeFi Wallet", "USDCUSD")]) == 3
