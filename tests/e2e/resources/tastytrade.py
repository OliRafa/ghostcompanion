"""Real-ticker Tastytrade transaction fixtures for end-to-end tests.

Ghostfolio validates every activity's symbol against its data source (YAHOO),
so these fixtures use real tickers. The corporate actions themselves (split
ratios, dividend amounts) are synthetic — we only need valid symbols; the values
we assert on are the ones our code computes and persists.
"""

import datetime
from decimal import Decimal

from tastytrade.account import Transaction

_UTC = datetime.timezone.utc


def _transaction(**overrides) -> Transaction:
    defaults = {
        "id": overrides["id"],
        "account_number": "E2E00001",
        "action": None,
        "description": "",
        "value": Decimal("0.0"),
        "net_value": Decimal("0.0"),
        "is_estimated_fee": True,
        "price": None,
        "quantity": None,
        "symbol": None,
    }
    return Transaction(**{**defaults, **overrides})


def _trade(
    id: int, symbol: str, quantity: str, price: str, day: datetime.date
) -> Transaction:
    total = Decimal(quantity) * Decimal(price)
    return _transaction(
        id=id,
        action="Buy to Open",
        transaction_type="Trade",
        transaction_sub_type="Buy to Open",
        description=f"Bought {quantity} {symbol} @ {price}",
        executed_at=datetime.datetime(day.year, day.month, day.day, 15, tzinfo=_UTC),
        transaction_date=day,
        symbol=symbol,
        quantity=Decimal(quantity),
        price=Decimal(price),
        value=-total,
        net_value=-total,
    )


def _split_leg(
    id: int, symbol: str, action: str, sub_type: str, quantity: str, day: datetime.date
) -> Transaction:
    # Split legs carry no price; the ratio comes from the buy/sell quantities.
    second = 20 if action == "Sell to Close" else 21
    return _transaction(
        id=id,
        action=action,
        transaction_type="Receive Deliver",
        transaction_sub_type=sub_type,
        description=f"{sub_type}: {action} {quantity} {symbol}",
        executed_at=datetime.datetime(
            day.year, day.month, day.day, 18, 36, second, tzinfo=_UTC
        ),
        transaction_date=day,
        symbol=symbol,
        quantity=Decimal(quantity),
    )


# AAPL: bought 8 shares, then a 1-for-4 reverse split -> 2 shares @ 4x the price.
_aapl_buy = _trade(1001, "AAPL", "8.0", "100.00", datetime.date(2023, 1, 3))
_aapl_reverse_split = [
    _split_leg(
        1002, "AAPL", "Sell to Close", "Reverse Split", "8.0", datetime.date(2024, 6, 3)
    ),
    _split_leg(
        1003, "AAPL", "Buy to Open", "Reverse Split", "2.0", datetime.date(2024, 6, 3)
    ),
]

# MSFT: bought 5 shares, then a 2-for-1 forward split -> 10 shares @ half the price.
_msft_buy = _trade(2001, "MSFT", "5.0", "100.00", datetime.date(2023, 2, 1))
_msft_forward_split = [
    _split_leg(
        2002, "MSFT", "Sell to Close", "Forward Split", "5.0", datetime.date(2024, 5, 1)
    ),
    _split_leg(
        2003, "MSFT", "Buy to Open", "Forward Split", "10.0", datetime.date(2024, 5, 1)
    ),
]

# KO: a received cash dividend (enriched with a per-share price by the Yahoo stub).
_ko_dividend = _transaction(
    id=3001,
    action=None,
    transaction_type="Money Movement",
    transaction_sub_type="Dividend",
    description="KO dividend",
    executed_at=datetime.datetime(2023, 6, 1, 22, tzinfo=_UTC),
    transaction_date=datetime.date(2023, 6, 1),
    symbol="KO",
    value=Decimal("25.0"),
    net_value=Decimal("25.0"),
)

# Symbol change: 3 shares bought under FB, later renamed to META.
_fb_buy = _trade(4001, "FB", "3.0", "100.00", datetime.date(2023, 3, 1))
_fb_to_meta_symbol_change = [
    _transaction(
        id=4002,
        action="Sell to Close",
        transaction_type="Receive Deliver",
        transaction_sub_type="Symbol Change",
        description="Symbol change: Close FB",
        executed_at=datetime.datetime(2023, 7, 1, 18, 36, 20, tzinfo=_UTC),
        transaction_date=datetime.date(2023, 7, 1),
        symbol="FB",
        quantity=Decimal("3.0"),
    ),
    _transaction(
        id=4003,
        action="Buy to Open",
        transaction_type="Receive Deliver",
        transaction_sub_type="Symbol Change",
        description="Symbol change: Open META",
        executed_at=datetime.datetime(2023, 7, 1, 18, 36, 21, tzinfo=_UTC),
        transaction_date=datetime.date(2023, 7, 1),
        symbol="META",
        quantity=Decimal("3.0"),
    ),
]


TRANSACTIONS: list[Transaction] = [
    _aapl_buy,
    *_aapl_reverse_split,
    _msft_buy,
    *_msft_forward_split,
    _ko_dividend,
    _fb_buy,
    *_fb_to_meta_symbol_change,
]
