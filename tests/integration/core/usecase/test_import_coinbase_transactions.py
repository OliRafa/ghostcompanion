from pytest import fixture

from tastytrade_ghostfolio.core.entity.symbol_change import SymbolChange
from tastytrade_ghostfolio.core.entity.transaction_type import TransactionType
from tastytrade_ghostfolio.core.provider.coinbase import CoinbaseProvider
from tastytrade_ghostfolio.core.usecase.import_coinbase_transactions import (
    ImportCoinbaseTransactions,
)
from tastytrade_ghostfolio.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from tests.infra.coinbase_api import InMemoryCoinbaseApi
from tests.infra.ghostfolio_api import InMemoryGhostfolioApi
from tests.infra.symbol_mapping_repository import InMemorySymbolMappingRepository


class ImportCoinbaseTransactionsFactory:
    @fixture(autouse=True)
    def initialize_import_coinbase_transactions(self):
        self.import_coinbase_transactions = ImportCoinbaseTransactions(
            CoinbaseProvider(InMemoryCoinbaseApi()),
            GhostfolioAdapter(InMemoryGhostfolioApi()),
            InMemorySymbolMappingRepository(),
        )


class TestImportCoinbaseTransactions(ImportCoinbaseTransactionsFactory):
    def should_add_assets_to_portfolio(self):
        portfolio = self.import_coinbase_transactions.execute()

        assert portfolio.get_symbols() is not None

    def should_use_yahoo_as_data_source(self):
        portfolio = self.import_coinbase_transactions.execute()

        trades = portfolio.get_trades("BTCUSD")

        assert all(trade.data_source == "YAHOO" for trade in trades)

    def should_adapt_symbols_for_yahoo_data_source(self):
        portfolio = self.import_coinbase_transactions.execute()

        assets = portfolio.get_symbols()

        assert assets == ["ETHUSD", "BTCUSD"]

    def when_coin_has_0_network_fee_should_not_create_sells_for_it(self):
        portfolio = self.import_coinbase_transactions.execute()

        trades = portfolio.get_trades("ETHUSD")

        assert all(
            trade.quantity > 0
            for trade in trades
            if trade.transaction_type == TransactionType.SELL
        )

    def should_take_into_account_symbol_maps(self):
        symbol_mapping_repository = InMemorySymbolMappingRepository(
            [SymbolChange(old_symbol="ETHUSD", new_symbol="NOTETH")]
        )
        self.import_coinbase_transactions.symbol_mapping_repository = (
            symbol_mapping_repository
        )

        portfolio = self.import_coinbase_transactions.execute()

        assert portfolio.has_asset("NOTETH") is True
