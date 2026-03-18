"""Integration tests for ImportTastytradeCashBalances use case."""

from datetime import date
from decimal import Decimal

from ghostcompanion.core.provider.tastytrade import TastytradeProvider
from ghostcompanion.core.usecase.import_tastytrade_cash_balances import (
    ImportTastytradeCashBalances,
)
from ghostcompanion.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from tests.infra.ghostfolio_api import InMemoryGhostfolioApi
from tests.infra.tastytrade_api import InMemoryTastytradeApi


class TestImportTastytradeCashBalances:
    """Integration tests using InMemory repositories."""

    def setup_method(self) -> None:
        """Set up fresh InMemory repositories for each test."""
        self.tastytrade_api = InMemoryTastytradeApi()
        self.ghostfolio_api = InMemoryGhostfolioApi()
        self.tastytrade_provider = TastytradeProvider(self.tastytrade_api)
        self.ghostfolio = GhostfolioAdapter(self.ghostfolio_api)

    def _get_tastytrade_account_id(self) -> str:
        """Helper to get the Tastytrade account ID."""
        accounts = self.ghostfolio_api.get_accounts()
        tastytrade_account = next(
            (a for a in accounts if a["name"] == "Tastytrade"), None
        )
        assert tastytrade_account is not None, "Tastytrade account not found"
        return tastytrade_account["id"]

    def should_create_balance_when_none_exists(self) -> None:
        """When Ghostfolio has no balances, create a new balance."""
        # Arrange - Set current cash balance from provider
        self.tastytrade_api.set_current_cash_balance(Decimal("1500.00"))

        use_case = ImportTastytradeCashBalances(
            self.tastytrade_provider, self.ghostfolio
        )

        # Act
        result = use_case.execute("Tastytrade")

        # Assert
        assert result.amount == Decimal("1500.00")
        assert result.date == date.today()

        # Verify Ghostfolio has the balance
        ghostfolio_balances = self.ghostfolio_api.get_balances_for_account(
            self._get_tastytrade_account_id()
        )
        assert len(ghostfolio_balances) == 1
        assert ghostfolio_balances[0]["value"] == 1500.0

    def should_update_balance_when_value_differs(self) -> None:
        """When provider value differs from latest Ghostfolio balance, create new entry."""
        # Arrange - First create an initial balance
        self.tastytrade_api.set_current_cash_balance(Decimal("1000.00"))
        use_case = ImportTastytradeCashBalances(
            self.tastytrade_provider, self.ghostfolio
        )
        use_case.execute("Tastytrade")

        # Now change the provider value
        self.tastytrade_api.set_current_cash_balance(Decimal("1200.00"))

        # Act
        result = use_case.execute("Tastytrade")

        # Assert
        assert result.amount == Decimal("1200.00")

        # Verify Ghostfolio now has 2 balances (historical + new)
        ghostfolio_balances = self.ghostfolio_api.get_balances_for_account(
            self._get_tastytrade_account_id()
        )
        assert len(ghostfolio_balances) == 2

    def should_skip_update_when_values_match(self) -> None:
        """When provider value matches latest Ghostfolio balance, do nothing."""
        # Arrange - Create initial balance
        self.tastytrade_api.set_current_cash_balance(Decimal("1000.00"))
        use_case = ImportTastytradeCashBalances(
            self.tastytrade_provider, self.ghostfolio
        )
        use_case.execute("Tastytrade")

        # Act - Run again with same value
        result = use_case.execute("Tastytrade")

        # Assert
        assert result.amount == Decimal("1000.00")

        # Verify Ghostfolio still has only 1 balance
        ghostfolio_balances = self.ghostfolio_api.get_balances_for_account(
            self._get_tastytrade_account_id()
        )
        assert len(ghostfolio_balances) == 1

    def should_handle_zero_balance(self) -> None:
        """Test that zero cash balance is handled correctly."""
        # Arrange
        self.tastytrade_api.set_current_cash_balance(Decimal("0.00"))

        use_case = ImportTastytradeCashBalances(
            self.tastytrade_provider, self.ghostfolio
        )

        # Act
        result = use_case.execute("Tastytrade")

        # Assert
        assert result.amount == Decimal("0.00")

        # Verify Ghostfolio has the zero balance
        ghostfolio_balances = self.ghostfolio_api.get_balances_for_account(
            self._get_tastytrade_account_id()
        )
        assert len(ghostfolio_balances) == 1
        assert ghostfolio_balances[0]["value"] == 0.0

    def should_handle_negative_balance(self) -> None:
        """Test that negative cash balance (margin) is handled correctly."""
        # Arrange
        self.tastytrade_api.set_current_cash_balance(Decimal("-500.00"))

        use_case = ImportTastytradeCashBalances(
            self.tastytrade_provider, self.ghostfolio
        )

        # Act
        result = use_case.execute("Tastytrade")

        # Assert
        assert result.amount == Decimal("-500.00")

        # Verify Ghostfolio has the negative balance
        ghostfolio_balances = self.ghostfolio_api.get_balances_for_account(
            self._get_tastytrade_account_id()
        )
        assert len(ghostfolio_balances) == 1
        assert ghostfolio_balances[0]["value"] == -500.0

    def should_use_account_currency(self) -> None:
        """Test that currency from Ghostfolio account is used."""
        # Arrange
        self.tastytrade_api.set_current_cash_balance(Decimal("1000.00"))

        use_case = ImportTastytradeCashBalances(
            self.tastytrade_provider, self.ghostfolio
        )

        # Act
        result = use_case.execute("Tastytrade")

        # Assert
        assert result.currency == "USD"  # Default currency

    def should_preserve_historical_balances(self) -> None:
        """Test that historical balances are never deleted, only new ones added."""
        # Arrange - Create multiple balance updates over time
        self.tastytrade_api.set_current_cash_balance(Decimal("1000.00"))
        use_case = ImportTastytradeCashBalances(
            self.tastytrade_provider, self.ghostfolio
        )
        use_case.execute("Tastytrade")

        self.tastytrade_api.set_current_cash_balance(Decimal("1200.00"))
        use_case.execute("Tastytrade")

        self.tastytrade_api.set_current_cash_balance(Decimal("1100.00"))
        use_case.execute("Tastytrade")

        # Act - One more update
        self.tastytrade_api.set_current_cash_balance(Decimal("1300.00"))
        result = use_case.execute("Tastytrade")

        # Assert - Should have 4 balances (all historical entries preserved)
        ghostfolio_balances = self.ghostfolio_api.get_balances_for_account(
            self._get_tastytrade_account_id()
        )
        assert len(ghostfolio_balances) == 4
        assert result.amount == Decimal("1300.00")
