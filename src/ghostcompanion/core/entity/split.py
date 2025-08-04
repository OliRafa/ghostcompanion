from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class Split(BaseModel):
    effective_date: date
    ratio: Decimal
    symbol: str
