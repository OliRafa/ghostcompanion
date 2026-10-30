from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class BinanceRecord(BaseModel):
    """One change to a Binance balance, as its Transaction Records export lists
    it. A trade is several records of the same second: what was bought, what
    was sold and the fee, each in its own coin."""

    model_config = ConfigDict(frozen=True)

    account: str
    change: Decimal
    coin: str
    executed_at: datetime
    operation: str
    remark: str = ""
