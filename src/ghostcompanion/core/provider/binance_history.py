import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from ghostcompanion.core.entity.binance import BinanceRecord

# Fiat Binance has traded coins against: a trade with one on a side is a plain
# buy or sell in it, while fiat itself is cash, not a holding.
FIAT = frozenset(
    "AED ARS AUD BRL CHF COP CZK EUR GBP HUF IDR INR JPY KZT MXN NGN PLN RON RUB"
    " SEK TRY UAH USD ZAR".split()
)

# A trade's records share their second: what was given is negative, what was
# got positive, and the fee has operations of its own.
_TRADE_OPERATIONS = frozenset(
    {
        "Binance Convert",
        "Buy",
        "Fee",
        "Sell",
        "Transaction Buy",
        "Transaction Fee",
        "Transaction Revenue",
        "Transaction Sold",
        "Transaction Spend",
    }
)
_FEE_OPERATIONS = frozenset({"Fee", "Transaction Fee"})
_GIFT_OPERATIONS = frozenset({"Airdrop Assets", "Distribution"})
_CRYPTO_TRANSFER_OPERATIONS = frozenset({"Deposit", "Withdraw"})
_FIAT_TRANSFER_OPERATIONS = frozenset(
    {"Fiat Deposit", "Fiat Withdraw", "Fiat Withdrawal"}
)
# A renamed coin leaves as this operation, and arrives under its new name as a
# distribution remarked "<OLD> to <NEW>", possibly months apart.
_RENAME_OPERATION = "Token Swap - Redenomination/Rebranding"
_RENAME_REMARK = re.compile(r"^(\S+) to (\S+)$")


@dataclass(frozen=True)
class BinanceExchange:
    """A trade: one coin given for another, and the fees it cost."""

    reference: str
    executed_at: datetime
    given: str
    given_quantity: Decimal
    got: str
    got_quantity: Decimal
    fees: dict[str, Decimal]


@dataclass(frozen=True)
class BinanceHistory:
    """What the exports say, renamed coins under their new names. `transfers`
    are crypto deposits and withdrawals; `unread` counts the records of each
    operation nothing books."""

    renames: dict[str, str] = field(default_factory=dict)
    exchanges: list[BinanceExchange] = field(default_factory=list)
    gifts: list[BinanceRecord] = field(default_factory=list)
    transfers: list[BinanceRecord] = field(default_factory=list)
    unread: Counter[str] = field(default_factory=Counter)


def read_history(records: list[BinanceRecord]) -> BinanceHistory:
    renames, renamed = _find_renames(records)
    history = BinanceHistory(renames=renames)
    trade_records: dict[datetime, list[BinanceRecord]] = defaultdict(list)
    for record in records:
        if record in renamed:
            continue
        record = record.model_copy(
            update={"coin": renames.get(record.coin, record.coin)}
        )
        if record.operation in _TRADE_OPERATIONS:
            trade_records[record.executed_at].append(record)
        elif record.operation in _GIFT_OPERATIONS and record.change > 0:
            history.gifts.append(record)
        elif record.operation in _CRYPTO_TRANSFER_OPERATIONS:
            # Fiat moves by the same operations, but only as cash.
            if record.coin not in FIAT:
                history.transfers.append(record)
        elif record.operation not in _FIAT_TRANSFER_OPERATIONS:
            history.unread[record.operation] += 1

    for executed_at, same_second in trade_records.items():
        exchange = _exchange_of_records(executed_at, same_second)
        if exchange:
            history.exchanges.append(exchange)
        else:
            history.unread["trade"] += 1

    return history


def exchanges_of_trades(
    symbol: dict[str, Any], trades: list[dict[str, Any]]
) -> list[BinanceExchange]:
    """The exchanges of the API's trades on `symbol`, one per order, its fills
    together."""
    orders: defaultdict[int, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        orders[trade["orderId"]].append(trade)

    exchanges = []
    base, quote = symbol["baseAsset"], symbol["quoteAsset"]
    for order_id, fills in orders.items():
        base_quantity = sum((Decimal(x["qty"]) for x in fills), Decimal("0"))
        quote_quantity = sum((Decimal(x["quoteQty"]) for x in fills), Decimal("0"))
        fees: defaultdict[str, Decimal] = defaultdict(Decimal)
        for fill in fills:
            fees[fill["commissionAsset"]] += Decimal(fill["commission"])
        bought = fills[0]["isBuyer"]
        exchanges.append(
            BinanceExchange(
                reference=f"binance-order-{order_id}",
                executed_at=datetime.fromtimestamp(
                    min(x["time"] for x in fills) / 1000, tz=timezone.utc
                ),
                given=quote if bought else base,
                given_quantity=quote_quantity if bought else base_quantity,
                got=base if bought else quote,
                got_quantity=base_quantity if bought else quote_quantity,
                fees=dict(fees),
            )
        )

    return exchanges


def _find_renames(
    records: list[BinanceRecord],
) -> tuple[dict[str, str], set[BinanceRecord]]:
    """Coins renamed as a whole, and the records that renamed them. A rename that
    changed the amount (a redenomination) isn't one, and stays unread."""
    renames: dict[str, str] = {}
    renamed: set[BinanceRecord] = set()
    for arrived in records:
        match = _RENAME_REMARK.match(arrived.remark)
        if not match or arrived.coin != match[2] or arrived.change <= 0:
            continue
        left = next(
            (
                x
                for x in records
                if x.operation == _RENAME_OPERATION
                and x.coin == match[1]
                and x.change == -arrived.change
                and x not in renamed
            ),
            None,
        )
        if left:
            renames[match[1]] = match[2]
            renamed |= {arrived, left}

    return renames, renamed


def _exchange_of_records(
    executed_at: datetime, records: list[BinanceRecord]
) -> BinanceExchange | None:
    given: defaultdict[str, Decimal] = defaultdict(Decimal)
    got: defaultdict[str, Decimal] = defaultdict(Decimal)
    fees: defaultdict[str, Decimal] = defaultdict(Decimal)
    for record in records:
        if record.operation in _FEE_OPERATIONS:
            fees[record.coin] -= record.change
        elif record.change < 0:
            given[record.coin] -= record.change
        else:
            got[record.coin] += record.change

    # Two pairs traded in the same second can't be told apart.
    if len(given) != 1 or len(got) != 1:
        return None
    [(given_coin, given_quantity)] = given.items()
    [(got_coin, got_quantity)] = got.items()
    return BinanceExchange(
        reference=f"binance-{executed_at.isoformat()}",
        executed_at=executed_at,
        given=given_coin,
        given_quantity=given_quantity,
        got=got_coin,
        got_quantity=got_quantity,
        fees=dict(fees),
    )
