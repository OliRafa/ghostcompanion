import logging
from typing import final

from ghostcompanion.core.entity.onchain_movement import OnChainMovement
from ghostcompanion.core.entity.portfolio import Portfolio
from ghostcompanion.core.entity.symbol_change import SymbolChange
from ghostcompanion.core.provider.blockchain import BlockchainProvider
from ghostcompanion.core.provider.coinbase import CoinbaseProvider
from ghostcompanion.core.provider.evm_wallet import EvmWalletProvider
from ghostcompanion.core.usecase.crypto_ledger import CryptoLedger
from ghostcompanion.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from ghostcompanion.repositories.config import ConfigRepository

logger = logging.getLogger(__name__)


@final
class ImportCryptoTransactions:
    """Builds the portfolios of Coinbase and of the configured self-custody wallets.

    They're built together because coins move between them: both sides of a
    transfer come from one transaction, seen once by each account.
    """

    def __init__(
        self,
        blockchain_provider: BlockchainProvider,
        coinbase_provider: CoinbaseProvider | None,
        config_repository: ConfigRepository,
        ghostfolio: GhostfolioAdapter,
        evm_wallet_provider: EvmWalletProvider | None = None,
    ) -> None:
        self.blockchain_provider = blockchain_provider
        self.coinbase_provider = coinbase_provider
        self.config_repository = config_repository
        self.ghostfolio = ghostfolio
        self.evm_wallet_provider = evm_wallet_provider

    def execute(self) -> list[Portfolio]:
        portfolios: dict[str, Portfolio] = {}
        movements: list[OnChainMovement] = []

        if self.coinbase_provider:
            logger.info("Started getting all Coinbase transactions")
            account_name = CoinbaseProvider.ACCOUNT_NAME
            portfolio = Portfolio(self.ghostfolio.get_or_create_account(account_name))
            for coin in self.coinbase_provider.get_coins():
                portfolio.add_asset(coin, self.coinbase_provider.get_trades(coin))
                movements += self.coinbase_provider.get_movements(coin)

            portfolios[account_name] = portfolio

        wallets = self.config_repository.get_wallets()
        tokens = self.config_repository.get_tokens()
        tracked_symbols: dict[str, set[str]] = {}
        for wallet in wallets:
            logger.info(f"Started getting `{wallet.name}` on-chain transactions")
            account = self.ghostfolio.get_or_create_account(wallet.name)
            portfolios[wallet.name] = Portfolio(account)
            if wallet.is_evm:
                if self.evm_wallet_provider is None:
                    raise ValueError(
                        f"`{wallet.name}` is an EVM wallet, which needs ALCHEMY_API_KEY"
                    )
                movements += self.evm_wallet_provider.get_movements(wallet, tokens)
                tracked_symbols[wallet.name] = {
                    x.symbol for x in tokens if x.network in wallet.networks
                }
            else:
                movements += self.blockchain_provider.get_movements(wallet)
                tracked_symbols[wallet.name] = {
                    x.native_symbol for x in wallet.networks
                }

        CryptoLedger(portfolios, wallets, tracked_symbols).book(movements)

        symbol_mappings = self.config_repository.get_symbol_mappings()
        for portfolio in portfolios.values():
            # Only Yahoo names coins as pairs; other sources (e.g. a price proxy
            # behind GHOSTFOLIO) know them by the symbol they were configured with.
            portfolio.adapt_symbol_changes(
                [
                    SymbolChange(
                        old_symbol=coin,
                        new_symbol=self.ghostfolio.adapt_crypto_symbol(coin),
                    )
                    for coin in portfolio.get_symbols()
                    if all(x.data_source == "YAHOO" for x in portfolio.get_trades(coin))
                ]
            )
            if symbol_mappings:
                logger.info("Handling symbol changes from config file")
                portfolio.adapt_symbol_changes(symbol_mappings)

        return list(portfolios.values())
