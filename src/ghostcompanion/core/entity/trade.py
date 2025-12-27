from datetime import datetime
from decimal import Decimal
from typing import Self, override

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
    def __eq__(self, other: datetime | Self) -> bool:
        """To implement 'in' operator"""
        if (
            self.executed_at.date() == other.executed_at.date()
            and self.quantity == other.quantity
            and self.symbol == other.symbol
            and self.unit_price == other.unit_price
            and self.fee == other.fee
        ):
            return True

        return False
