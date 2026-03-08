import datetime
from decimal import Decimal

from tastytrade.account import Transaction

from ghostcompanion.core.ports.tastytrade import TastytradePort
from tests.resources.tastytrade.tastytrade_transactions import TRANSACTIONS


class InMemoryTastytradeApi(TastytradePort):
    """In-memory mock of Tastytrade SDK for testing"""

    def __init__(self):
        self._trades = TRANSACTIONS

    def get_trades_history(self) -> list[Transaction]:
        return self._trades


class InMemoryTastytradeApiWithExtraTransaction(TastytradePort):
    """In-memory mock that includes an extra non-trade transaction for testing filtering"""

    def __init__(self):
        # Copy existing transactions and add a non-trade entry
        self._trades = list(TRANSACTIONS)
        self._trades.append(
            Transaction(
                id=999,
                account_number="",
                transaction_type="Another",
                transaction_sub_type="Another Sub Type",
                description="",
                executed_at=datetime.datetime.now(),
                transaction_date=datetime.date.today(),
                value=Decimal("0.0"),
                net_value=Decimal("0.0"),
                is_estimated_fee=True,
                symbol=None,
            )
        )

    def get_trades_history(self) -> list[Transaction]:
        return self._trades


class InMemoryTastytradeApiWithDividendOnlyAsset(TastytradePort):
    """In-memory mock that includes a dividend-only asset (no trades) for testing asset detection"""

    def __init__(self):
        # Copy existing transactions and add a dividend-only entry
        self._trades = list(TRANSACTIONS)
        self._trades.append(
            Transaction(
                id=1000,
                action="Buy to Open",
                account_number="",
                transaction_type="Receive Deliver",
                transaction_sub_type="Dividend",
                description="",
                executed_at=datetime.datetime.now(),
                transaction_date=datetime.date.today(),
                value=Decimal("0.0"),
                net_value=Decimal("0.0"),
                is_estimated_fee=True,
                symbol="STOCKC",
                quantity=Decimal("0.1"),
                price=Decimal("10.0"),
            )
        )

    def get_trades_history(self) -> list[Transaction]:
        return self._trades
