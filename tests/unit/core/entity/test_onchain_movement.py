from datetime import datetime, timezone
from decimal import Decimal

from pydantic import ValidationError
from pytest import raises

from ghostcompanion.core.entity.onchain_movement import OnChainMovement


def build_movement(**fields) -> OnChainMovement:
    return OnChainMovement(
        account="DeFi Wallet",
        currency="USD",
        executed_at=datetime(2026, 10, 2, tzinfo=timezone.utc),
        market_unit_price=Decimal("1"),
        quantity=Decimal("0.613407"),
        symbol="USDC",
        **fields,
    )


class TestInterest:
    def should_name_the_market_that_added_it(self):
        movement = build_movement(interest=True, market="Aave")

        assert movement.market == "Aave"

    def when_no_market_added_it_should_raise_exception(self):
        with raises(ValidationError, match="market"):
            build_movement(interest=True)


class TestDebt:
    def should_name_the_market_it_is_owed_to(self):
        movement = build_movement(debt=True, market="Aave")

        assert movement.market == "Aave"

    def when_owed_to_no_market_should_raise_exception(self):
        with raises(ValidationError, match="market"):
            build_movement(debt=True)


class TestTransactionId:
    def should_drop_the_0x_prefix_and_lower_the_case(self):
        movement = build_movement(transaction_id="0xABCD")

        assert movement.transaction_id == "abcd"
