"""End-to-end: sync the current Tastytrade cash balance into a real Ghostfolio
instance and read the persisted account balance back."""

from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.provider.tastytrade import TastytradeProvider
from ghostcompanion.core.usecase.import_tastytrade_cash_balances import (
    ImportTastytradeCashBalances,
)
from tests.e2e.resources.stubs import InMemoryTastytradeApi


class TastytradeCashBalancesE2E:
    ACCOUNT_NAME = "Tastytrade"

    @fixture(autouse=True)
    def setup(self, ghostfolio):
        self.ghostfolio = ghostfolio

    def import_balance(self, amount: str):
        provider = TastytradeProvider(
            InMemoryTastytradeApi(cash_balance=Decimal(amount))
        )
        ImportTastytradeCashBalances(provider, self.ghostfolio).execute()

    def latest_balance(self) -> Decimal | None:
        account = self.ghostfolio.get_or_create_account(self.ACCOUNT_NAME)
        balance = self.ghostfolio.get_latest_account_balance(account.id)
        return balance.amount if balance else None


class TestCashBalanceImport(TastytradeCashBalancesE2E):
    def should_persist_current_cash_balance(self):
        self.import_balance("1234.56")

        assert self.latest_balance() == Decimal("1234.56")

    def should_persist_new_entry_when_balance_changes(self):
        self.import_balance("1000.00")
        self.import_balance("2500.75")

        assert self.latest_balance() == Decimal("2500.75")
