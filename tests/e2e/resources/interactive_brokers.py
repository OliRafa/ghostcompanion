"""Deterministic in-memory Interactive Brokers source for end-to-end tests.

Ghostfolio validates every activity's symbol against its data source (YAHOO)
and rejects unknown tickers, so this fixture uses REAL tickers. The trade prices
and quantities are synthetic — we only need valid symbols; the values we assert
on are the ones our code computes and persists.
"""

import datetime
from decimal import Decimal
from typing import final, override

from ibflex import (
    AssetClass,
    BuySell,
    ChangeInDividendAccrual,
    Code,
    OpenClose,
    OrderType,
    Trade,
    TradeType,
)

from ghostcompanion.core.ports.interactive_brokers import InteractiveBrokersPort


def _trade(
    symbol: str,
    buy_sell: BuySell,
    quantity: str,
    price: str,
    day: datetime.date,
    commission: str = "-1.00",
    open_close: OpenClose = OpenClose.OPEN,
) -> Trade:
    signed_quantity = Decimal(quantity)
    trade_money = signed_quantity * Decimal(price)
    return Trade(
        transactionType=TradeType.EXCHTRADE,
        openCloseIndicator=open_close,
        buySell=buy_sell,
        orderType=OrderType.MARKET,
        assetCategory=AssetClass.STOCK,
        accountId="U000E2E01",
        currency="USD",
        fxRateToBase=Decimal("1"),
        symbol=symbol,
        description=symbol,
        multiplier=Decimal("1"),
        reportDate=day,
        tradeDate=day,
        tradeTime=None,
        settleDateTarget=day + datetime.timedelta(days=1),
        quantity=signed_quantity,
        tradePrice=Decimal(price),
        tradeMoney=trade_money,
        proceeds=-trade_money,
        netCash=-trade_money + Decimal(commission),
        taxes=Decimal("0"),
        ibCommission=Decimal(commission),
        ibCommissionCurrency="USD",
        closePrice=Decimal(price),
        notes=(),
        cost=trade_money - Decimal(commission),
        mtmPnl=Decimal("0"),
        origTradePrice=Decimal("0"),
        orderTime=datetime.datetime(day.year, day.month, day.day, 14, 30, 0),
        dateTime=datetime.datetime(day.year, day.month, day.day, 14, 30, 1),
        underlyingSymbol=symbol,
        accruedInt=Decimal("0"),
    )


# AAPL: bought 10 @ 150.00
_aapl_buy = _trade("AAPL", BuySell.BUY, "10", "150.00", datetime.date(2025, 11, 3))

# MSFT: bought 5 @ 300.00
_msft_buy = _trade("MSFT", BuySell.BUY, "5", "300.00", datetime.date(2025, 11, 4))

# NVDA: bought 8 @ 120.00, then sold 3 @ 130.00
_nvda_buy = _trade("NVDA", BuySell.BUY, "8", "120.00", datetime.date(2025, 11, 5))
_nvda_sell = _trade(
    "NVDA",
    BuySell.SELL,
    "-3",
    "130.00",
    datetime.date(2025, 12, 1),
    open_close=OpenClose.CLOSE,
)

# AAPL: a posted dividend accrual (0.25/share on 10 shares).
_aapl_dividend = ChangeInDividendAccrual(
    date=datetime.date(2025, 11, 20),
    assetCategory=AssetClass.STOCK,
    currency="USD",
    fxRateToBase=Decimal("1"),
    accountId="U000E2E01",
    symbol="AAPL",
    description="AAPL",
    reportDate=datetime.date(2025, 11, 21),
    exDate=datetime.date(2025, 11, 20),
    payDate=datetime.date(2025, 12, 1),
    quantity=Decimal("10"),
    tax=Decimal("0"),
    fee=Decimal("0"),
    grossRate=Decimal("0.25"),
    grossAmount=Decimal("2.50"),
    netAmount=Decimal("2.50"),
    code=(Code.POSTACCRUAL,),
    underlyingSymbol="AAPL",
    multiplier=Decimal("1"),
    actionID=Decimal("100000001"),
)

TRADES: list[Trade] = [_aapl_buy, _msft_buy, _nvda_buy, _nvda_sell]
DIVIDENDS: list[ChangeInDividendAccrual] = [_aapl_dividend]


@final
class InMemoryInteractiveBrokersApi(InteractiveBrokersPort):
    def __init__(
        self,
        trades: list[Trade] = TRADES,
        dividends: list[ChangeInDividendAccrual] = DIVIDENDS,
        cash_balance: Decimal = Decimal("5000.00"),
    ) -> None:
        self._trades = trades
        self._dividends = dividends
        self._cash_balance = cash_balance

    def set_cash_balance(self, balance: Decimal) -> None:
        self._cash_balance = balance

    @override
    def get_current_cash_balance(self) -> Decimal:
        return self._cash_balance

    @override
    def get_dividends_by_symbol(self, symbol: str) -> list[ChangeInDividendAccrual]:
        return [dividend for dividend in self._dividends if dividend.symbol == symbol]

    @override
    def get_symbols(self) -> list[str]:
        stock_trades = filter(
            lambda trade: trade.assetCategory == AssetClass.STOCK, self._trades
        )
        return list(set(filter(None, (trade.symbol for trade in stock_trades))))

    @override
    def get_trades_by_symbol(self, symbol: str) -> list[Trade]:
        return [trade for trade in self._trades if trade.symbol == symbol]
