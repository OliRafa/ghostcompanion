import datetime
from decimal import Decimal

from pydantic import BaseModel


class DividendInfo(BaseModel):
    asset: str
    ex_dividend_date: datetime.date
    unit_price: Decimal
