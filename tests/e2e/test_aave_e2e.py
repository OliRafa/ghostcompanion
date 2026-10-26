"""End-to-end: import USDC an EVM wallet supplied to Aave on Base, part of it
withdrawn since, into a real Ghostfolio instance.

The wallet got 1000 USDC, supplied 600 and withdrew 200, so its movements leave
400 in Aave. Aave holds 400.5 for it now: the 0.5 USDC earned is bought for
nothing. All of it stays in the wallet's account, where supplying and withdrawing
book nothing.
"""

from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.entity.wallet import Network, Wallet
from ghostcompanion.core.provider.blockchain import BlockchainProvider
from ghostcompanion.core.provider.evm_wallet import EvmWalletProvider
from ghostcompanion.core.usecase.export_portfolio import ExportPortfolio
from ghostcompanion.core.usecase.import_crypto_transactions import (
    ImportCryptoTransactions,
)
from ghostcompanion.infra.market_prices.market_price_adapter import MarketPriceAdapter
from tests.e2e.resources.aave import (
    CHANGES,
    RECEIPTS,
    TRANSFERS,
    USDC_BASE,
    USDC_RESERVE,
    WALLET,
)
from tests.infra.blockchain_api import InMemoryBlockchainApi
from tests.infra.config_repository import InMemoryConfigRepository
from tests.infra.evm_chain_api import InMemoryEvmChainApi
from tests.infra.lending_market_api import InMemoryLendingMarketApi
from tests.infra.yahoo_finance_api import InMemoryYahooFinanceApi

DEFI_WALLET = Wallet(name="DeFi Wallet", network=Network.BASE, addresses=(WALLET,))


class AaveE2E:
    @fixture(autouse=True)
    def imported_portfolios(self, ghostfolio):
        self.ghostfolio = ghostfolio
        self.import_and_export()

    def import_and_export(self):
        market_prices = MarketPriceAdapter(InMemoryYahooFinanceApi())
        lending_market = InMemoryLendingMarketApi([USDC_RESERVE], CHANGES)
        lending_market.set_position(WALLET, USDC_BASE, supplied="400.5")
        use_case = ImportCryptoTransactions(
            BlockchainProvider(InMemoryBlockchainApi([]), market_prices),
            None,
            InMemoryConfigRepository(wallets=[DEFI_WALLET]),
            self.ghostfolio,
            EvmWalletProvider(
                InMemoryEvmChainApi({Network.BASE: TRANSFERS}, RECEIPTS),
                market_prices,
                lending_market,
            ),
        )

        export_portfolio = ExportPortfolio(self.ghostfolio)
        self.portfolios = {x.account.name: x for x in use_case.execute()}
        for portfolio in self.portfolios.values():
            export_portfolio.execute(portfolio)

    def orders(self, account: str) -> list[tuple]:
        account_id = self.portfolios[account].account.id
        return sorted(
            (x.transaction_type.value, x.quantity, x.unit_price, x.description)
            for x in self.ghostfolio.get_orders_by_symbol(account_id, "USDCUSD")
        )


class TestLending(AaveE2E):
    def should_keep_supplied_and_withdrawn_usdc_in_the_wallet(self):
        assert list(self.portfolios) == ["DeFi Wallet"]
        assert [x[:2] + x[3:] for x in self.orders("DeFi Wallet")] == [
            ("BUY", Decimal("0.5"), "Interest earned on Aave"),
            ("BUY", Decimal("1000"), "Received"),
        ]

    def should_book_the_interest_earned(self):
        interest = [x for x in self.orders("DeFi Wallet") if x[3].startswith("Int")]

        assert interest == [
            ("BUY", Decimal("0.5"), Decimal("0"), "Interest earned on Aave")
        ]


class TestIdempotency(AaveE2E):
    def activity_ids(self) -> dict[str, list[str]]:
        return {
            account: sorted(
                x.id
                for x in self.ghostfolio.get_orders_by_symbol(
                    portfolio.account.id, "USDCUSD"
                )
            )
            for account, portfolio in self.portfolios.items()
        }

    def when_imported_again_should_leave_activities_untouched(self):
        ids_before = self.activity_ids()

        self.import_and_export()

        assert self.activity_ids() == ids_before
        assert len(ids_before["DeFi Wallet"]) == 2
