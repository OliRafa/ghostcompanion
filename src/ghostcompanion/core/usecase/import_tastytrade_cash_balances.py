from ghostcompanion.core.entity.cash_balance import CashBalance
from ghostcompanion.core.provider.tastytrade import TastytradeProvider
from ghostcompanion.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter


class ImportTastytradeCashBalances:
    """
    Use case for importing current cash balance from Tastytrade to Ghostfolio.

    This use case synchronizes the current cash balance by:
    1. Getting the current cash balance from the provider
    2. Getting the latest balance from Ghostfolio
    3. Creating a new balance entry if the values differ
    4. Skipping if values are already in sync

    Historical balances are never deleted - only new entries are added
    when the cash balance changes.
    """

    def __init__(
        self,
        tastytrade_provider: TastytradeProvider,
        ghostfolio: GhostfolioAdapter,
    ):
        self.tastytrade_provider = tastytrade_provider
        self.ghostfolio = ghostfolio

    def execute(self, account_name: str = "Tastytrade") -> CashBalance:
        """
        Execute the cash balance import and synchronization.

        Args:
            account_name: The name of the Ghostfolio account (default "Tastytrade")

        Returns:
            CashBalance: The current cash balance from the provider
        """
        ghostfolio_account = self.ghostfolio.get_or_create_account(account_name)

        account_currency = (
            ghostfolio_account.currency if ghostfolio_account.currency else "USD"
        )

        # Get current balance from provider
        current_balance = self.tastytrade_provider.get_current_cash_balance(
            account_currency
        )

        # Get latest balance from Ghostfolio
        latest_balance = self.ghostfolio.get_latest_account_balance(
            ghostfolio_account.id
        )

        # Compare and update if different
        if self._should_update(current_balance, latest_balance):
            print(
                f"Updating cash balance: ${current_balance.amount} "
                f"(previous: ${latest_balance.amount if latest_balance else 'None'})"
            )
            self.ghostfolio.create_account_balance(
                ghostfolio_account.id,
                current_balance.date,
                current_balance.amount,
            )
        else:
            print("Cash balance is already up to date")

        return current_balance

    def _should_update(self, current: CashBalance, latest: CashBalance | None) -> bool:
        """Determine if a new balance entry should be created.

        Returns True if:
        - No previous balance exists (latest is None)
        - Current amount differs from latest amount

        Historical balances are never deleted - we simply add a new entry
        when the value changes.
        """
        if latest is None:
            return True

        return current.amount != latest.amount
