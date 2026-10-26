from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from ghostcompanion.core.entity.wallet import Network


class LendingReserve(BaseModel):
    """A coin a lending market lends out on one network, and the two tokens it
    keeps each account's share in: one for what was supplied, which grows with
    the interest earned, and one for what is owed, which grows with the
    interest due."""

    model_config = ConfigDict(frozen=True)

    network: Network
    asset: str
    supply_token: str
    debt_token: str
    decimals: int


class LendingPosition(BaseModel):
    model_config = ConfigDict(frozen=True)

    reserve: LendingReserve
    supplied: Decimal
    borrowed: Decimal


class LendingChange(BaseModel):
    """What one transaction did to an owner's position in a reserve, in coins, as
    the market's own token events tell it: what was supplied (positive) or
    withdrawn through the market, supply tokens received (positive) or sent
    without going through it, what was borrowed (positive) or repaid, and the
    interest the market added to each side as it did so."""

    model_config = ConfigDict(frozen=True)

    reserve: LendingReserve
    supplied: Decimal = Decimal("0")
    transferred: Decimal = Decimal("0")
    interest_earned: Decimal = Decimal("0")
    borrowed: Decimal = Decimal("0")
    interest_due: Decimal = Decimal("0")


class LendingBalance(BaseModel):
    """What an account holds in a lending market at `observed_at`, interest
    included: a coin supplied (positive) or a debt owed (negative)."""

    model_config = ConfigDict(frozen=True)

    account: str
    currency: str
    data_source: str
    market: str
    observed_at: datetime
    quantity: Decimal
    symbol: str
