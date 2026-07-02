"""End-to-end: sync the current Coinbase cash balance into a real Ghostfolio
instance and read the persisted account balance back."""

from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.provider.coinbase import CoinbaseProvider
from ghostcompanion.core.usecase.import_coinbase_cash_balances import (
    ImportCoinbaseCashBalances,
)
from tests.e2e.resources.coinbase import InMemoryCoinbaseApi


class CoinbaseCashBalancesE2E:
    ACCOUNT_NAME = "Coinbase"

    @fixture(autouse=True)
    def setup(self, ghostfolio):
        self.ghostfolio = ghostfolio

    def import_balance(self, amount: str):
        provider = CoinbaseProvider(InMemoryCoinbaseApi(cash_balance=Decimal(amount)))
        ImportCoinbaseCashBalances(provider, self.ghostfolio).execute()

    def latest_balance(self) -> Decimal | None:
        account = self.ghostfolio.get_or_create_account(self.ACCOUNT_NAME)
        balance = self.ghostfolio.get_latest_account_balance(account.id)
        return balance.amount if balance else None


class TestCashBalanceImport(CoinbaseCashBalancesE2E):
    def should_persist_current_cash_balance(self):
        self.import_balance("1234.56")

        assert self.latest_balance() == Decimal("1234.56")

    def should_persist_new_entry_when_balance_changes(self):
        self.import_balance("1000.00")
        self.import_balance("2500.75")

        assert self.latest_balance() == Decimal("2500.75")
