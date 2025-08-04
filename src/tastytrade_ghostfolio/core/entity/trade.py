from datetime import datetime
from decimal import Decimal
from typing import Optional, Self

from pydantic import BaseModel, Field, computed_field

from tastytrade_ghostfolio.core.entity.transaction_type import TransactionType


class Trade(BaseModel):
    currency: Optional[str] = Field("USD")
    description: Optional[str] = Field(None)
    data_source: str = Field("YAHOO", alias="dataSource")
    executed_at: datetime
    fee: Decimal
    id: Optional[str] = Field(None)
    inner_quantity: Optional[Decimal] = Field(
        None, alias="quantity", exclude=True, repr=False
    )
    inner_unit_price: Optional[Decimal] = Field(
        None, alias="unit_price", exclude=True, repr=False
    )
    symbol: str
    transaction_type: TransactionType
    value: Optional[Decimal] = Field(None)

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

    def __eq__(self, other: datetime | Self) -> bool:
        """To implement 'in' operator"""
        if (
            self.executed_at.date() == other.executed_at.date()
            and self.quantity == other.quantity
            and self.symbol == other.symbol
            and self.unit_price == other.unit_price
        ):
            return True

        return False
