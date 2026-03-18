"""Unit tests for TastytradeProvider cash balance methods."""
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from ghostcompanion.core.entity.cash_balance import CashBalance
from ghostcompanion.core.ports.tastytrade import TastytradePort
from ghostcompanion.core.provider.tastytrade import TastytradeProvider


class TestGetCurrentCashBalance:
    """Test the get_current_cash_balance method."""

    def should_return_current_cash_balance(self) -> None:
        """Test that the provider returns the current cash balance from API."""
        mock_api = MagicMock(spec=TastytradePort)
        mock_api.get_current_cash_balance.return_value = Decimal("1500.50")

        provider = TastytradeProvider(mock_api)
        result = provider.get_current_cash_balance("USD")

        assert isinstance(result, CashBalance)
        assert result.date == date.today()
        assert result.amount == Decimal("1500.50")
        assert result.currency == "USD"

    def should_use_provided_currency(self) -> None:
        """Test that the currency parameter is used in the returned balance."""
        mock_api = MagicMock(spec=TastytradePort)
        mock_api.get_current_cash_balance.return_value = Decimal("2000.00")

        provider = TastytradeProvider(mock_api)
        result = provider.get_current_cash_balance("EUR")

        assert result.currency == "EUR"
        assert result.amount == Decimal("2000.00")

    def should_default_to_usd(self) -> None:
        """Test that USD is used as default currency."""
        mock_api = MagicMock(spec=TastytradePort)
        mock_api.get_current_cash_balance.return_value = Decimal("1000.00")

        provider = TastytradeProvider(mock_api)
        result = provider.get_current_cash_balance()

        assert result.currency == "USD"

    def should_handle_zero_balance(self) -> None:
        """Test that zero cash balance is handled correctly."""
        mock_api = MagicMock(spec=TastytradePort)
        mock_api.get_current_cash_balance.return_value = Decimal("0")

        provider = TastytradeProvider(mock_api)
        result = provider.get_current_cash_balance("USD")

        assert result.amount == Decimal("0")

    def should_handle_negative_balance_margin(self) -> None:
        """Test that negative cash balance (margin) is handled correctly."""
        mock_api = MagicMock(spec=TastytradePort)
        mock_api.get_current_cash_balance.return_value = Decimal("-500.00")

        provider = TastytradeProvider(mock_api)
        result = provider.get_current_cash_balance("USD")

        assert result.amount == Decimal("-500.00")

    def should_call_api_to_get_current_balance(self) -> None:
        """Test that the API is called to get the current cash balance."""
        mock_api = MagicMock(spec=TastytradePort)
        mock_api.get_current_cash_balance.return_value = Decimal("1000.00")
        mock_api.get_trades_history.return_value = []

        provider = TastytradeProvider(mock_api)
        provider.get_current_cash_balance("GBP")

        mock_api.get_current_cash_balance.assert_called_once()
