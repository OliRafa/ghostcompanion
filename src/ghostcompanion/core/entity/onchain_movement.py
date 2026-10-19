from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class OnChainMovement(BaseModel):
    """Coins entering or leaving one of the user's accounts through the blockchain.

    `quantity` is what was credited (positive) or debited (negative) excluding
    the network fee, which is paid on top of it by the sending account. Both
    sides of a transfer between the user's own accounts share `transaction_id`.
    `market_unit_price` is None for a coin with no price of its own, which can
    only be booked from a swap.
    """

    model_config = ConfigDict(frozen=True)

    account: str
    currency: str
    data_source: str = "YAHOO"
    destination_address: str | None = None
    executed_at: datetime
    fee: Decimal = Decimal("0")
    market_unit_price: Decimal | None
    quantity: Decimal
    symbol: str
    transaction_id: str | None = None

    @field_validator("transaction_id")
    @classmethod
    def _normalize_transaction_id(cls, transaction_id: str | None) -> str | None:
        # Sources disagree on case and on the 0x prefix of EVM hashes: Coinbase
        # drops it for Ethereum but keeps it for Base.
        if transaction_id is None:
            return None
        return transaction_id.lower().removeprefix("0x")
