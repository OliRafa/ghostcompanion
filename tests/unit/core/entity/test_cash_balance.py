from datetime import date
from decimal import Decimal

import pytest

from ghostcompanion.core.entity.cash_balance import CashBalance


class TestCashBalanceCreation:
    def should_create_cash_balance_with_valid_data(self) -> None:
        balance = CashBalance(
            date=date(2024, 1, 15), amount=Decimal("1250.50"), currency="USD"
        )

        assert balance.date == date(2024, 1, 15)
        assert balance.amount == Decimal("1250.50")
        assert balance.currency == "USD"

    def should_create_cash_balance_with_negative_amount(self) -> None:
        """Negative amounts are allowed for margin accounts."""
        balance = CashBalance(
            date=date(2024, 1, 15), amount=Decimal("-500.00"), currency="USD"
        )

        assert balance.amount == Decimal("-500.00")

    def should_raise_error_for_invalid_currency_length(self) -> None:
        with pytest.raises(ValueError, match="Currency must be 3-letter ISO code"):
            CashBalance(
                date=date(2024, 1, 15), amount=Decimal("1000.00"), currency="US"
            )

    def should_raise_error_for_non_alphabetic_currency(self) -> None:
        with pytest.raises(ValueError, match="Currency must be 3-letter ISO code"):
            CashBalance(
                date=date(2024, 1, 15), amount=Decimal("1000.00"), currency="U1D"
            )

    def should_accept_various_currencies(self) -> None:
        currencies = ["USD", "EUR", "GBP", "JPY", "CAD", "CHF"]

        for currency_code in currencies:
            balance = CashBalance(
                date=date(2024, 1, 15),
                amount=Decimal("1000.00"),
                currency=currency_code,
            )
            assert balance.currency == currency_code


class TestCashBalanceComparison:
    def should_compare_balances_by_date(self) -> None:
        balance1 = CashBalance(
            date=date(2024, 1, 1), amount=Decimal("1000.00"), currency="USD"
        )
        balance2 = CashBalance(
            date=date(2024, 1, 15), amount=Decimal("1200.00"), currency="USD"
        )
        balance3 = CashBalance(
            date=date(2024, 1, 1), amount=Decimal("800.00"), currency="USD"
        )

        # Same date, different amounts - should be equal (frozen dataclass compares all fields)
        assert balance1 != balance3
        # Different dates - should not be equal
        assert balance1 != balance2
