from datetime import datetime
from decimal import Decimal
from typing import override

from pydantic import BaseModel, Field, computed_field

from ghostcompanion.core.entity.transaction_type import TransactionType


class Trade(BaseModel):
    currency: str | None = "USD"
    description: str | None = None
    data_source: str = Field(default="YAHOO", alias="dataSource")
    executed_at: datetime
    fee: Decimal
    id: str | None = None
    inner_quantity: Decimal | None = Field(
        default=None, alias="quantity", exclude=True, repr=False
    )
    inner_unit_price: Decimal | None = Field(
        default=None, alias="unit_price", exclude=True, repr=False
    )
    symbol: str
    transaction_type: TransactionType
    value: Decimal | None = None

    def change_symbol(self, value: str):
        self.symbol = value

    @computed_field
    @property
    def quantity(self) -> Decimal:
        if self.inner_quantity is None:
            return round(self.value / self.unit_price, 14)

        return self.inner_quantity

    @quantity.setter
    def quantity(self, value: Decimal):
        self.inner_quantity = value

    @computed_field
    @property
    def unit_price(self) -> Decimal:
        if self.inner_unit_price is None:
            return round(self.value / self.quantity, 14)

        return self.inner_unit_price

    @unit_price.setter
    def unit_price(self, value: Decimal):
        self.inner_unit_price = value

    @override
    def __eq__(self, other: object) -> bool:
        """To implement 'in' operator"""
        if not isinstance(other, Trade):
            return NotImplemented

        # Ghostfolio stores amounts as doubles, so a trade read back from it only
        # keeps the digits a double can hold. Comparing at that precision is also
        # how Ghostfolio itself detects duplicate activities.
        return (
            self.executed_at.date() == other.executed_at.date()
            and self.symbol == other.symbol
            and self.transaction_type == other.transaction_type
            and float(self.quantity) == float(other.quantity)
            and float(self.unit_price) == float(other.unit_price)
            and float(self.fee) == float(other.fee)
        )
