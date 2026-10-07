import logging
from pathlib import Path

from ghostcompanion.configs.logging_config import configure_logging
from ghostcompanion.configs.settings import Settings
from ghostcompanion.core.provider.blockchain import BlockchainProvider
from ghostcompanion.core.provider.coinbase import CoinbaseProvider
from ghostcompanion.core.provider.interactive_brokers import InteractiveBrokersProvider
from ghostcompanion.core.provider.tastytrade import TastytradeProvider
from ghostcompanion.core.usecase.export_portfolio import ExportPortfolio
from ghostcompanion.core.usecase.import_coinbase_cash_balances import (
    ImportCoinbaseCashBalances,
)
from ghostcompanion.core.usecase.import_crypto_transactions import (
    ImportCryptoTransactions,
)
from ghostcompanion.core.usecase.import_interactive_brokers_cash_balances import (
    ImportInteractiveBrokersCashBalances,
)
from ghostcompanion.core.usecase.import_interactive_brokers_transactions import (
    ImportInteractiveBrokersTransactions,
)
from ghostcompanion.core.usecase.import_tastytrade_cash_balances import (
    ImportTastytradeCashBalances,
)
from ghostcompanion.core.usecase.import_tastytrade_transactions import (
    ImportTastytradeTransactions,
)
from ghostcompanion.infra.blockchain.mempool_space_api import MempoolSpaceApi
from ghostcompanion.infra.coinbase.coinbase_api import CoinbaseApi
from ghostcompanion.infra.dividends_provider.dividends_provider_adapter import (
    DividendsProviderAdapter,
)
from ghostcompanion.infra.dividends_provider.yahoo_finance_api import YahooFinanceApi
from ghostcompanion.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from ghostcompanion.infra.ghostfolio.ghostfolio_api import GhostfolioApi
from ghostcompanion.infra.interactive_brokers.interactive_brokers_api import (
    InteractiveBrokersApi,
)
from ghostcompanion.infra.market_prices.market_price_adapter import MarketPriceAdapter
from ghostcompanion.infra.tastytrade.tastytrade_adapter import TastytradeAdapter
from ghostcompanion.infra.tastytrade.tastytrade_api import TastytradeApi
from ghostcompanion.repositories.config import ConfigRepository

logger = logging.getLogger(__name__)


def _should_run_coinbase_importer() -> bool:
    if Settings.Coinbase.API_KEY and Settings.Coinbase.SECRET:
        return True

    return False


def _should_run_tastytrade_importer() -> bool:
    if Settings.Tastytrade.CLIENT_SECRET and Settings.Tastytrade.REFRESH_TOKEN:
        return True

    return False


def _should_run_interactive_brokers_importer() -> bool:
    if Settings.InteractiveBrokers.QUERY and Settings.InteractiveBrokers.TOKEN:
        return True

    return False


if __name__ == "__main__":
    configure_logging(Settings.LOG_LEVEL)
    logger.info("Starting Ghostcompanion")

    ghostfolio = GhostfolioAdapter(GhostfolioApi())
    config_repository = ConfigRepository(Path(Settings.CONFIG_PATH))
    export_portfolio = ExportPortfolio(ghostfolio)

    coinbase_provider = (
        CoinbaseProvider(CoinbaseApi()) if _should_run_coinbase_importer() else None
    )
    if coinbase_provider or config_repository.get_wallets():
        import_crypto_transactions = ImportCryptoTransactions(
            BlockchainProvider(
                MempoolSpaceApi(), MarketPriceAdapter(YahooFinanceApi())
            ),
            coinbase_provider,
            config_repository,
            ghostfolio,
        )

        for portfolio in import_crypto_transactions.execute():
            export_portfolio.execute(portfolio)

    if coinbase_provider:
        # Import cash balances from Coinbase
        logger.info("Starting Coinbase cash balance import")
        import_coinbase_cash = ImportCoinbaseCashBalances(coinbase_provider, ghostfolio)
        import_coinbase_cash.execute()
        logger.info("Coinbase cash balance import complete")

    if _should_run_tastytrade_importer():
        tastytrade_api = TastytradeAdapter(TastytradeApi())
        tastytrade_provider = TastytradeProvider(tastytrade_api)
        dividends_provider = DividendsProviderAdapter(YahooFinanceApi())
        import_tastytrade_transactions = ImportTastytradeTransactions(
            dividends_provider,
            ghostfolio,
            config_repository,
            tastytrade_provider,
        )

        portfolio = import_tastytrade_transactions.execute()
        export_portfolio.execute(portfolio)

        # Import cash balances from Tastytrade
        logger.info("Starting cash balance import")
        import_cash_balances = ImportTastytradeCashBalances(
            tastytrade_provider, ghostfolio
        )
        import_cash_balances.execute()
        logger.info("Cash balance import complete")

    if _should_run_interactive_brokers_importer():
        interactive_brokers = InteractiveBrokersProvider(InteractiveBrokersApi())
        dividends_provider = DividendsProviderAdapter(YahooFinanceApi())
        import_interactive_brokers_transactions = ImportInteractiveBrokersTransactions(
            interactive_brokers, ghostfolio, config_repository
        )

        portfolio = import_interactive_brokers_transactions.execute()
        export_portfolio.execute(portfolio)

        # Import cash balances from Interactive Brokers
        logger.info("Starting Interactive Brokers cash balance import")
        import_ibkr_cash = ImportInteractiveBrokersCashBalances(
            interactive_brokers, ghostfolio
        )
        import_ibkr_cash.execute()
        logger.info("Interactive Brokers cash balance import complete")

    logger.info("Done!")
