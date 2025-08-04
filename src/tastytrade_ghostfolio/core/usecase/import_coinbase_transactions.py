from tastytrade_ghostfolio.core.entity.portfolio import Portfolio
from tastytrade_ghostfolio.core.entity.symbol_change import SymbolChange
from tastytrade_ghostfolio.core.entity.trade import Trade
from tastytrade_ghostfolio.core.provider.coinbase import CoinbaseProvider
from tastytrade_ghostfolio.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from tastytrade_ghostfolio.repositories.symbol_mapping import (
    SymbolMappingRepository,
    SymbolMappingsNotFoundException,
)


class ImportCoinbaseTransactions:
    def __init__(
        self,
        coinbase_provider: CoinbaseProvider,
        ghostfolio: GhostfolioAdapter,
        symbol_mapping_repository: SymbolMappingRepository,
    ) -> None:
        self.coinbase_provider = coinbase_provider
        self.ghostfolio = ghostfolio
        self.symbol_mapping_repository = symbol_mapping_repository

    def execute(self) -> Portfolio:
        ghostfolio_account = self.ghostfolio.get_or_create_account("Coinbase")
        portfolio = Portfolio(ghostfolio_account)

        print("Started getting all Coinbase transactions...")
        coins = self.coinbase_provider.get_coins()
        for coin in coins:
            trades = self.coinbase_provider.get_trades(coin)
            trades = self._filter_zero_network_fees(trades)

            portfolio.add_asset(coin, trades)

            symbol_change = SymbolChange(
                old_symbol=coin, new_symbol=self.ghostfolio.adapt_crypto_symbol(coin)
            )
            portfolio.adapt_symbol_changes([symbol_change])

        try:
            symbol_mappings = self.symbol_mapping_repository.get_symbol_mappings()
            print("Handling symbol changes from mapping file...")
            portfolio.adapt_symbol_changes(symbol_mappings)

        except SymbolMappingsNotFoundException:
            print("Skipping symbol changes from mapping file, as no file was found.")

        return portfolio

    @staticmethod
    def _filter_zero_network_fees(trades: list[Trade]) -> list[Trade]:
        return list(
            filter(
                lambda trade: not (
                    trade.description == "Network Fee" and trade.quantity == 0
                ),
                trades,
            )
        )
