from datetime import datetime, timedelta
from decimal import Decimal

from ghostcompanion.core.entity.trade import Trade
from ghostcompanion.core.entity.transaction_type import TransactionType


class TestTrade:
    def should_change_symbol(self):
        trade = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.0"),
            quantity=Decimal("0.0"),
            symbol="TEST",
            transaction_type=TransactionType.BUY,
            unit_price=Decimal("0.0"),
        )

        trade.change_symbol("NEW")
        assert trade.symbol == "NEW"


class TestQuantity:
    def when_dividend_has_unit_price_and_value_should_calculate_quantity(self):
        trade = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.0"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("12.5"),
            value=Decimal("25.0"),
        )

        assert trade.quantity == Decimal("2.0")

    def when_calculating_quantity_should_round_it_to_14_decimal_places(self):
        trade = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.21"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.234"),
            value=Decimal("1.4"),
        )

        assert trade.quantity == Decimal("5.98290598290598")


class TestUnitPrice:
    def when_trade_has_quantity_and_value_should_calculate_unit_price(self):
        trade = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.21"),
            symbol="TEST",
            transaction_type=TransactionType.BUY,
            quantity=Decimal("5.98290598290598"),
            value=Decimal("1.4"),
        )

        assert trade.unit_price == Decimal("0.234")

    def when_given_unit_price_should_not_recalculate_it(self):
        trade = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.21"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.234"),
            value=Decimal("1.4"),
        )

        assert trade.unit_price == Decimal("0.234")

    def when_value_is_o_unit_price_should_be_0(self):
        trade = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.21"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            quantity=Decimal("5.98290598290598"),
            value=Decimal("0"),
        )

        assert trade.unit_price == Decimal("0")


class TestEquals:
    def should_ignore_trailing_zeros_when_comparing(self):
        trade_a = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.210000"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.234000"),
            value=Decimal("1.4"),
        )

        trade_b = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.21"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.234"),
            value=Decimal("1.4"),
        )

        assert trade_a == trade_b

    def should_take_fee_into_consideration(self):
        trade_a = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.234000"),
            value=Decimal("1.4"),
        )

        trade_b = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.21"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.234"),
            value=Decimal("1.4"),
        )

        assert trade_a != trade_b

    def should_take_execution_date_into_consideration(self):
        trade_a = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.21"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.234000"),
            value=Decimal("1.4"),
        )

        trade_b = Trade(
            executed_at=datetime.now() - timedelta(days=1),
            fee=Decimal("0.21"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.234"),
            value=Decimal("1.4"),
        )

        assert trade_a != trade_b

    def should_not_take_execution_time_into_consideration(self):
        trade_a = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.21"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.234000"),
            value=Decimal("1.4"),
        )

        trade_b = Trade(
            executed_at=datetime.now() - timedelta(minutes=1),
            fee=Decimal("0.21"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.234"),
            value=Decimal("1.4"),
        )

        assert trade_a == trade_b

    def should_take_quantity_into_consideration(self):
        trade_a = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.21"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.234000"),
            quantity=Decimal("1.01"),
        )

        trade_b = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.21"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.234"),
            quantity=Decimal("1.02"),
        )

        assert trade_a != trade_b

    def should_take_unity_price_into_consideration(self):
        trade_a = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.21"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.234"),
            quantity=Decimal("1.01"),
        )

        trade_b = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.21"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.233"),
            quantity=Decimal("1.01"),
        )

        assert trade_a != trade_b

    def should_take_symbol_into_consideration(self):
        trade_a = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.21"),
            symbol="TEST",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.234"),
            quantity=Decimal("1.02"),
        )

        trade_b = Trade(
            executed_at=datetime.now(),
            fee=Decimal("0.21"),
            symbol="TEST1",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.234"),
            quantity=Decimal("1.02"),
        )

        assert trade_a != trade_b

    def should_take_transaction_type_into_consideration(self):
        buy = build_trade(TransactionType.BUY)
        sell = build_trade(TransactionType.SELL)

        assert buy != sell

    def when_amounts_differ_beyond_double_precision_should_be_equal(self):
        computed = build_trade(unit_price=Decimal("2156.76810466827243"))
        # What Ghostfolio returns after storing it as a double.
        stored = build_trade(unit_price=Decimal("2156.7681046682724"))

        assert computed == stored

    def when_amounts_differ_within_double_precision_should_not_be_equal(self):
        computed = build_trade(unit_price=Decimal("2156.7681046682"))
        stored = build_trade(unit_price=Decimal("2156.7681046683"))

        assert computed != stored

    def when_compared_with_other_types_should_not_be_equal(self):
        assert build_trade() != "TEST"


def build_trade(
    transaction_type: TransactionType = TransactionType.BUY,
    unit_price: Decimal = Decimal("0.234"),
) -> Trade:
    return Trade(
        executed_at=datetime(2024, 1, 1, 12),
        fee=Decimal("0.21"),
        quantity=Decimal("1.02"),
        symbol="TEST",
        transaction_type=transaction_type,
        unit_price=unit_price,
    )
