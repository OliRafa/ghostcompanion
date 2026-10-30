from decimal import Decimal
from pathlib import Path

from pytest import fixture

from ghostcompanion.core.entity.portfolio import Portfolio
from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.entity.wallet import Network, Wallet
from ghostcompanion.core.provider.binance import BinanceProvider
from ghostcompanion.core.provider.blockchain import BlockchainProvider
from ghostcompanion.core.usecase.import_crypto_transactions import (
    ImportCryptoTransactions,
)
from ghostcompanion.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from ghostcompanion.infra.market_prices.market_price_adapter import MarketPriceAdapter
from ghostcompanion.repositories.binance_transaction_records import (
    BinanceTransactionRecords,
)
from tests.infra.binance_api import InMemoryBinanceApi
from tests.infra.blockchain_api import InMemoryBlockchainApi
from tests.infra.config_repository import InMemoryConfigRepository
from tests.infra.ghostfolio_api import InMemoryGhostfolioApi
from tests.infra.yahoo_finance_api import InMemoryYahooFinanceApi
from tests.resources.binance.api import BALANCES, PRICE_HISTORIES, WITHDRAWALS

COLD_STORAGE_ADDRESS = "bc1qcoldstorage00000000000000000000000000001"
BINANCE_HOT_ADDRESS = "bc1qbinancehot00000000000000000000000000000"
WITHDRAWAL_TXID = "b1" * 32

COLD_STORAGE = Wallet(
    name="Cold Storage", network=Network.BITCOIN, addresses=(COLD_STORAGE_ADDRESS,)
)

# Sent from Binance's hot wallet to Cold Storage after the exports end.
WITHDRAWAL_TO_COLD_STORAGE = {
    "id": "w-2003",
    "amount": "0.01",
    "transactionFee": "0.0005",
    "coin": "BTC",
    "status": 6,
    "address": COLD_STORAGE_ADDRESS,
    "txId": WITHDRAWAL_TXID,
    "applyTime": "2023-01-10 11:58:00",
    "completeTime": "2023-01-10 12:00:00",
    "network": "BTC",
    "transferType": 0,
}
COLD_STORAGE_RECEIPT = {
    "txid": WITHDRAWAL_TXID,
    "status": {"confirmed": True, "block_height": 771000, "block_time": 1673352300},
    "fee": 2100,
    "vin": [
        {
            "prevout": {"scriptpubkey_address": BINANCE_HOT_ADDRESS, "value": 9000000},
            "is_coinbase": False,
        }
    ],
    "vout": [
        {"scriptpubkey_address": COLD_STORAGE_ADDRESS, "value": 1000000},
        {"scriptpubkey_address": BINANCE_HOT_ADDRESS, "value": 7997900},
    ],
}


class ImportBinanceTransactionsFactory:
    @fixture(autouse=True)
    def initialize_import(self):
        market_prices = MarketPriceAdapter(InMemoryYahooFinanceApi(PRICE_HISTORIES))
        binance_api = InMemoryBinanceApi(
            balances={**BALANCES, "BTC": Decimal("0.06323187")},
            withdrawals=WITHDRAWALS + [WITHDRAWAL_TO_COLD_STORAGE],
        )
        records = BinanceTransactionRecords(Path("tests/resources/binance"))
        self.import_crypto_transactions = ImportCryptoTransactions(
            BlockchainProvider(
                InMemoryBlockchainApi([COLD_STORAGE_RECEIPT]), market_prices
            ),
            None,
            InMemoryConfigRepository(wallets=[COLD_STORAGE]),
            GhostfolioAdapter(InMemoryGhostfolioApi()),
            binance_provider=BinanceProvider(
                binance_api, market_prices, records.get_records()
            ),
        )

    def portfolio(self, account: str) -> Portfolio:
        portfolios = self.import_crypto_transactions.execute()
        return next(x for x in portfolios if x.account.name == account)


class TestImportBinanceTransactions(ImportBinanceTransactionsFactory):
    def should_book_binance_in_its_own_account(self):
        portfolio = self.portfolio("Binance")

        assert set(portfolio.get_symbols()) == {
            "BTCUSD",
            "ETHWUSD",
            "LTCUSD",
            "XLMUSD",
            "XNOUSD",
            "XVGUSD",
        }

    def should_book_trades_against_fiat_in_that_fiat(self):
        trades = self.portfolio("Binance").get_trades("BTCUSD")

        assert {x.currency for x in trades if x.description is None} == {"BRL", "EUR"}

    def should_book_swaps_through_the_ledger(self):
        trades = self.portfolio("Binance").get_trades("LTCUSD")

        assert [(x.transaction_type, x.description) for x in trades] == [
            (TransactionType.BUY, "Received"),
            (TransactionType.SELL, "Swapped for BTC"),
        ]

    def when_coins_were_withdrawn_to_a_wallet_should_book_a_transfer(self):
        binance = self.portfolio("Binance").get_trades("BTCUSD")
        cold_storage = self.portfolio("Cold Storage").get_trades("BTCUSD")

        [sent] = [x for x in binance if x.description == "Transfer to Cold Storage"]
        [fee] = [
            x
            for x in binance
            if x.description == "Network Fee" and x.quantity == Decimal("0.0005")
        ]
        [received] = [
            x for x in cold_storage if x.description == "Transfer from Binance"
        ]
        assert sent.quantity == received.quantity == Decimal("0.01")
        assert fee.transaction_type == TransactionType.SELL
