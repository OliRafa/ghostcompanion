from datetime import datetime
from decimal import Decimal

from tastytrade_ghostfolio.core.entity.dividend_info import DividendInfo
from tastytrade_ghostfolio.core.entity.split import Split
from tastytrade_ghostfolio.core.entity.trade import Trade
from tastytrade_ghostfolio.core.entity.transaction_type import TransactionType
from tastytrade_ghostfolio.core.exceptions import TradeNotFoundException


class Asset:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self._trades: list[Trade] = []
        self._dividends: list[Trade] = []

    @property
    def trades(self) -> list[Trade]:
        return self._trades

    @property
    def dividends(self) -> list[Trade]:
        return self._dividends

    def add_trades(self, trades: list[Trade]):
        self._trades += trades
        self._trades = sorted(self._trades, key=lambda x: x.executed_at)

    def add_dividends(self, dividends: list[Trade], dividend_infos: list[DividendInfo]):
        dividend_taxes = filter(
            lambda x: x.transaction_type == TransactionType.FEE, dividends
        )
        dividends = list(
            filter(
                lambda x: x.transaction_type
                in (TransactionType.DIVIDEND, TransactionType.BUY),
                dividends,
            )
        )

        for dividend in dividends:
            match dividend.transaction_type:
                case TransactionType.BUY:
                    self._trades.append(dividend)

                case TransactionType.DIVIDEND:
                    dividend_info: DividendInfo = min(
                        dividend_infos,
                        key=lambda x: abs(
                            x.ex_dividend_date - dividend.executed_at.date()
                        ),
                    )
                    dividend.unit_price = dividend_info.unit_price

                    dividend_tax = next(
                        filter(
                            lambda x: x.executed_at == dividend.executed_at,
                            dividend_taxes,
                        ),
                        None,
                    )
                    if dividend_tax:
                        dividend.fee = dividend_tax.fee

                    self._dividends.append(dividend)

    def split_shares(self, split: Split):
        before_the_fact_trades = list(
            filter(lambda x: x.executed_at.date() <= split.effective_date, self._trades)
        )
        for trade in before_the_fact_trades:
            trade.quantity = trade.quantity * split.ratio
            trade.unit_price = trade.unit_price / split.ratio

    def has_trade(self, trade: Trade) -> bool:
        return trade in self._trades or trade in self._dividends

    def get_trade(
        self, executed_at: datetime, quantity: Decimal, symbol: str, unit_price: Decimal
    ) -> Trade:
        try:
            return next(
                filter(
                    lambda x: x.executed_at == executed_at
                    and x.quantity == quantity
                    and x.symbol == symbol
                    and x.unit_price == unit_price,
                    self._trades,
                )
            )

        except StopIteration:
            try:
                return next(
                    filter(
                        lambda x: x.executed_at == executed_at
                        and x.quantity == quantity
                        and x.symbol == symbol
                        and x.unit_price == unit_price,
                        self._dividends,
                    )
                )

            except StopIteration:
                raise TradeNotFoundException()

    def delete_trade(self, trade: Trade):
        _trade = self.get_trade(
            trade.executed_at, trade.quantity, trade.symbol, trade.unit_price
        )

        if _trade in self._dividends:
            self._dividends.remove(_trade)

        else:
            self._trades.remove(_trade)

    def change_symbol(self, symbol: str):
        self.symbol = symbol
        for trade in self._trades:
            trade.symbol = symbol
