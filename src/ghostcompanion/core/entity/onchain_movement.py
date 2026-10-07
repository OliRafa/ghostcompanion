from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class OnChainMovement(BaseModel):
    """Coins entering or leaving one of the user's accounts through the blockchain.

    `quantity` is what was credited (positive) or debited (negative) excluding
    the network fee, which is paid on top of it by the sending account. Both
    sides of a transfer between the user's own accounts share `transaction_id`.
    """

    model_config = ConfigDict(frozen=True)

    account: str
    currency: str
    destination_address: str | None = None
    executed_at: datetime
    fee: Decimal = Decimal("0")
    market_unit_price: Decimal
    quantity: Decimal
    symbol: str
    transaction_id: str | None = None
