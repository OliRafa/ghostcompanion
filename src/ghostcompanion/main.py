from ghostcompanion.configs.settings import Settings
from ghostcompanion.core.provider.coinbase import CoinbaseProvider
from ghostcompanion.core.usecase.export_portfolio import ExportPortfolio
from ghostcompanion.core.usecase.import_coinbase_transactions import (
    ImportCoinbaseTransactions,
)
from ghostcompanion.core.usecase.import_tastytrade_transactions import (
    ImportTastytradeTransactions,
)
from ghostcompanion.infra.coinbase.coinbase_api import CoinbaseApi
from ghostcompanion.infra.dividends_provider.dividends_provider_adapter import (
    DividendsProviderAdapter,
)
from ghostcompanion.infra.dividends_provider.yahoo_finance_api import (
    YahooFinanceApi,
)
from ghostcompanion.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from ghostcompanion.infra.ghostfolio.ghostfolio_api import GhostfolioApi
from ghostcompanion.infra.tastytrade.tastytrade_adapter import TastytradeAdapter
from ghostcompanion.infra.tastytrade.tastytrade_api import TastytradeApi
from ghostcompanion.repositories.symbol_mapping import SymbolMappingRepository


def _should_run_coinbase_importer() -> bool:
    if Settings.Coinbase.API_KEY and Settings.Coinbase.SECRET:
        return True

    return False


def _should_run_tastytrade_importer() -> bool:
    if Settings.Tastytrade.CLIENT_SECRET and Settings.Tastytrade.REFRESH_TOKEN:
        return True

    return False


if __name__ == "__main__":
    ghostfolio = GhostfolioAdapter(GhostfolioApi())
    symbol_mapping_repository = SymbolMappingRepository()
    export_portfolio = ExportPortfolio(ghostfolio)

    if _should_run_coinbase_importer():
        coinbase_provider = CoinbaseProvider(CoinbaseApi())
        import_coinbase_transactions = ImportCoinbaseTransactions(
            coinbase_provider, ghostfolio, symbol_mapping_repository
        )

        portfolio = import_coinbase_transactions.execute()
        export_portfolio.execute(portfolio)

    if _should_run_tastytrade_importer():
        tastytrade = TastytradeAdapter(TastytradeApi())
        dividends_provider = DividendsProviderAdapter(YahooFinanceApi())
        import_tastytrade_transactions = ImportTastytradeTransactions(
            dividends_provider, ghostfolio, symbol_mapping_repository, tastytrade
        )

        portfolio = import_tastytrade_transactions.execute()
        export_portfolio.execute(portfolio)

    print("Done!")
