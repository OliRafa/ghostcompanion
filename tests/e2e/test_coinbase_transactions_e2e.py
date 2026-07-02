"""End-to-end: import Coinbase crypto transactions into a real Ghostfolio
instance and read the persisted activities back.

The import turns each Coinbase coin code into a crypto pair via
``adapt_crypto_symbol`` (``BTC`` -> ``BTCUSD``). Ghostfolio's YAHOO data source
accepts that ``<COIN>USD`` form, so the buys/sells round-trip cleanly and can be
asserted against what actually landed in Ghostfolio.
"""

from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.provider.coinbase import CoinbaseProvider
from ghostcompanion.core.usecase.export_portfolio import ExportPortfolio
from ghostcompanion.core.usecase.import_coinbase_transactions import (
    ImportCoinbaseTransactions,
)
from tests.e2e.resources.coinbase import InMemoryCoinbaseApi
from tests.infra.symbol_mapping_repository import InMemorySymbolMappingRepository


class CoinbaseTransactionsE2E:
    @fixture(autouse=True)
    def imported_portfolio(self, ghostfolio):
        self.ghostfolio = ghostfolio
        provider = CoinbaseProvider(InMemoryCoinbaseApi())
        use_case = ImportCoinbaseTransactions(
            provider, ghostfolio, InMemorySymbolMappingRepository()
        )

        self.portfolio = use_case.execute()
        ExportPortfolio(ghostfolio).execute(self.portfolio)

    def orders_for(self, symbol: str):
        return self.ghostfolio.get_orders_by_symbol(self.portfolio.account.id, symbol)


class TestImportedSymbols(CoinbaseTransactionsE2E):
    def should_adapt_every_coin_into_a_usd_crypto_pair(self):
        for symbol in ("BTCUSD", "ETHUSD"):
            assert self.orders_for(symbol), f"{symbol} was not persisted"


class TestBitcoinTrades(CoinbaseTransactionsE2E):
    def should_persist_bitcoin_buys_and_sells(self):
        orders = self.orders_for("BTCUSD")

        buys = [o for o in orders if o.transaction_type == TransactionType.BUY]
        sells = [o for o in orders if o.transaction_type == TransactionType.SELL]
        assert len(buys) == 2
        assert len(sells) == 1

    def should_persist_bitcoin_buy_quantities_and_prices(self):
        orders = self.orders_for("BTCUSD")

        by_quantity = {o.quantity: o for o in orders}
        # 0.005 BTC bought for $200 -> $40000/coin.
        assert by_quantity[Decimal("0.005")].unit_price == Decimal("40000")
        # 0.003 BTC bought for $150 with a $3 fee.
        assert by_quantity[Decimal("0.003")].unit_price == Decimal("50000")
        assert by_quantity[Decimal("0.003")].fee == Decimal("3")


class TestEthereumTrades(CoinbaseTransactionsE2E):
    def should_persist_ethereum_buy(self):
        orders = self.orders_for("ETHUSD")

        buys = [o for o in orders if o.transaction_type == TransactionType.BUY]
        assert len(buys) == 1
        # 1.5 ETH bought for $3000 -> $2000/coin.
        assert buys[0].quantity == Decimal("1.5")
        assert buys[0].unit_price == Decimal("2000")
