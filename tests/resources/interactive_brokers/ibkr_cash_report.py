"""Test fixtures for Interactive Brokers cash balance data."""
from decimal import Decimal


# Mock CashReport data
class MockCashReport:
    """Mock CashReport object from ibflex library."""

    def __init__(self, ending_cash: Decimal):
        self.endingCash = ending_cash


# Test scenarios
CASH_REPORT_POSITIVE = MockCashReport(Decimal("5000.00"))
CASH_REPORT_NEGATIVE = MockCashReport(Decimal("-1000.00"))
CASH_REPORT_ZERO = MockCashReport(Decimal("0.00"))
CASH_REPORT_LARGE = MockCashReport(Decimal("100000.50"))

# Default test data
DEFAULT_CASH_BALANCE = CASH_REPORT_POSITIVE
