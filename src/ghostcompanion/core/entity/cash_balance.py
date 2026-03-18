from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class CashBalance(BaseModel):
    """Represents a cash balance for a specific date.

    Attributes:
        date: The date of the balance (end-of-day)
        amount: The cash amount in the account currency (can be negative for margin)
        currency: The currency code (e.g., "USD", "EUR")
        id: Optional Ghostfolio balance ID (present when loaded from Ghostfolio)
    """

    model_config = ConfigDict(frozen=True)

    date: date
    amount: Decimal
    currency: str = "USD"
    id: str | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate that currency is a 3-letter ISO code."""
        if len(v) != 3 or not v.isalpha():
            raise ValueError(f"Currency must be 3-letter ISO code, got: {v}")
        return v.upper()
