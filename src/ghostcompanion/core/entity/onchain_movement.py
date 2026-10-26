from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class OnChainMovement(BaseModel):
    """Coins entering or leaving one of the user's accounts through the blockchain.

    `quantity` is what was credited (positive) or debited (negative) excluding
    the network fee, which is paid on top of it by the sending account. Both
    sides of a transfer between the user's own accounts share `transaction_id`.
    `market_unit_price` is None for a coin with no price of its own, which can
    only be booked from a swap. `description` replaces the generic one the
    movement is booked with. `market` names the lending market a movement happened
    in on the account's behalf, to coins it holds for the account or a debt the
    account owes it, which are still the account's; `debt` marks the latter,
    whose coin the account owes rather than holds. `interest` marks what a
    lending market added to a position in that transaction without moving a coin:
    interest earned on a coin supplied (positive) or due on a debt (negative), or
    the rounding of its books, which `description` then names.
    """

    model_config = ConfigDict(frozen=True)

    account: str
    currency: str
    data_source: str = "YAHOO"
    debt: bool = False
    description: str | None = None
    destination_address: str | None = None
    executed_at: datetime
    fee: Decimal = Decimal("0")
    interest: bool = False
    market: str | None = None
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

    @model_validator(mode="after")
    def _lending_names_its_market(self) -> "OnChainMovement":
        if self.interest and self.market is None:
            raise ValueError("interest needs the `market` that added it")
        if self.debt and self.market is None:
            raise ValueError("a debt needs the `market` it's owed to")
        return self
