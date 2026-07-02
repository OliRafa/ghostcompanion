"""End-to-end: sync the current Interactive Brokers cash balance into a real
Ghostfolio instance and read the persisted account balance back."""

from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.provider.interactive_brokers import InteractiveBrokersProvider
from ghostcompanion.core.usecase.import_interactive_brokers_cash_balances import (
    ImportInteractiveBrokersCashBalances,
)
from tests.e2e.resources.interactive_brokers import InMemoryInteractiveBrokersApi


class InteractiveBrokersCashBalancesE2E:
    ACCOUNT_NAME = "Interactive Brokers"

    @fixture(autouse=True)
    def setup(self, ghostfolio):
        self.ghostfolio = ghostfolio

    def import_balance(self, amount: str):
        api = InMemoryInteractiveBrokersApi(cash_balance=Decimal(amount))
        provider = InteractiveBrokersProvider(api)
        ImportInteractiveBrokersCashBalances(provider, self.ghostfolio).execute()

    def latest_balance(self) -> Decimal | None:
        account = self.ghostfolio.get_or_create_account(self.ACCOUNT_NAME)
        balance = self.ghostfolio.get_latest_account_balance(account.id)
        return balance.amount if balance else None


class TestCashBalanceImport(InteractiveBrokersCashBalancesE2E):
    def should_persist_current_cash_balance(self):
        self.import_balance("4200.42")

        assert self.latest_balance() == Decimal("4200.42")

    def should_persist_new_entry_when_balance_changes(self):
        self.import_balance("1000.00")
        self.import_balance("3750.25")

        assert self.latest_balance() == Decimal("3750.25")
