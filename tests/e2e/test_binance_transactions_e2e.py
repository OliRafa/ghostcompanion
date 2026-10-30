"""End-to-end: import a Binance account, its trades from a Transaction Records
export and its transfers from the API, into a real Ghostfolio instance.

The export trades against BRL and EUR, which land as buys and sells in that
fiat, and coins for BTC, which the ledger books as swaps valued by BTC's close
(0.081234 BTC at $3480 for 2.5 LTC: $113.077728 per LTC).
"""

from decimal import Decimal
from pathlib import Path

from pytest import fixture

from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.provider.binance import BinanceProvider
from ghostcompanion.core.provider.blockchain import BlockchainProvider
from ghostcompanion.core.usecase.export_portfolio import ExportPortfolio
from ghostcompanion.core.usecase.import_crypto_transactions import (
    ImportCryptoTransactions,
)
from ghostcompanion.infra.market_prices.market_price_adapter import MarketPriceAdapter
from ghostcompanion.repositories.binance_transaction_records import (
    BinanceTransactionRecords,
)
from tests.infra.binance_api import InMemoryBinanceApi
from tests.infra.blockchain_api import InMemoryBlockchainApi
from tests.infra.config_repository import InMemoryConfigRepository
from tests.infra.yahoo_finance_api import InMemoryYahooFinanceApi
from tests.resources.binance.api import PRICE_HISTORIES

SYMBOLS = ("BTCUSD", "ETHWUSD", "LTCUSD", "XLMUSD", "XNOUSD", "XVGUSD")


class BinanceTransactionsE2E:
    @fixture(autouse=True)
    def imported_portfolio(self, ghostfolio):
        self.ghostfolio = ghostfolio
        self.import_and_export()

    def import_and_export(self):
        market_prices = MarketPriceAdapter(InMemoryYahooFinanceApi(PRICE_HISTORIES))
        records = BinanceTransactionRecords(Path("tests/resources/binance"))
        use_case = ImportCryptoTransactions(
            BlockchainProvider(InMemoryBlockchainApi([]), market_prices),
            None,
            InMemoryConfigRepository(),
            self.ghostfolio,
            binance_provider=BinanceProvider(
                InMemoryBinanceApi(), market_prices, records.get_records()
            ),
        )

        [self.portfolio] = use_case.execute()
        ExportPortfolio(self.ghostfolio).execute(self.portfolio)

    def orders_for(self, symbol: str):
        return self.ghostfolio.get_orders_by_symbol(self.portfolio.account.id, symbol)


class TestImportedSymbols(BinanceTransactionsE2E):
    def should_persist_every_coin_as_a_usd_crypto_pair(self):
        for symbol in SYMBOLS:
            assert self.orders_for(symbol), f"{symbol} was not persisted"


class TestFiatTrades(BinanceTransactionsE2E):
    def should_persist_a_buy_in_the_fiat_it_was_paid_with(self):
        [buy] = [
            x
            for x in self.orders_for("BTCUSD")
            if x.currency == "BRL" and x.transaction_type == TransactionType.BUY
        ]

        assert buy.quantity == Decimal("0.0057")
        # Ghostfolio keeps the unit price as a double.
        assert round(buy.quantity * buy.unit_price, 8) == Decimal("1574.63")

    def should_persist_a_coin_fee_as_a_sale_for_nothing(self):
        fees = [
            (x.quantity, x.unit_price)
            for x in self.orders_for("BTCUSD")
            if x.description == "Trading fee"
        ]

        assert (Decimal("0.0000057"), Decimal("0")) in fees


class TestSwaps(BinanceTransactionsE2E):
    def should_persist_a_coin_sold_for_btc_at_btc_value(self):
        [sell] = [
            x
            for x in self.orders_for("LTCUSD")
            if x.transaction_type == TransactionType.SELL
        ]

        assert sell.quantity == Decimal("2.5")
        assert sell.unit_price == Decimal("113.077728")
        assert sell.description == "Swapped for BTC"


class TestReimport(BinanceTransactionsE2E):
    def should_leave_the_activities_as_they_were(self):
        before = {x.id for symbol in SYMBOLS for x in self.orders_for(symbol)}

        self.import_and_export()

        after = {x.id for symbol in SYMBOLS for x in self.orders_for(symbol)}
        assert after == before
