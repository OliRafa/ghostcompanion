from collections.abc import Iterable
from decimal import Decimal
from itertools import chain
from typing import final

import ibflex

from ghostcompanion.core.entity.trade import Trade
from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.ports.interactive_brokers import InteractiveBrokersPort


@final
class InteractiveBrokersProvider:
    def __init__(self, interactive_brokers_api: InteractiveBrokersPort) -> None:
        self.interactive_brokers_api = interactive_brokers_api

    def get_symbols(self) -> list[str]:
        return self.interactive_brokers_api.get_symbols()

    def get_dividends(self, symbol: str | None = None) -> list[Trade]: ...

    def get_trades(self, symbol: str | None = None) -> list[Trade]:
        if symbol:
            trades = self.interactive_brokers_api.get_trades_by_symbol(symbol)

        else:
            trades = []

        cancels = list(
            filter(
                lambda x: x.buySell == ibflex.BuySell.CANCELBUY
                or x.buySell == ibflex.BuySell.CANCELSELL,
                trades,
            )
        )

        trades = list(
            filter(
                lambda x: x.buySell == ibflex.BuySell.BUY
                or x.buySell == ibflex.BuySell.SELL,
                trades,
            )
        )

        trades = self.__filter_canceled_trades(trades, cancels)
        return list(map(self.__adapt_trade, trades))

    def __adapt_trade(self, trade: ibflex.Trade) -> Trade:
        return Trade(
            currency=trade.currency,
            executed_at=trade.dateTime,
            fee=abs(trade.ibCommission or Decimal("0"))
            + abs(trade.taxes or Decimal("0")),
            quantity=abs(trade.quantity or Decimal("0")),
            unit_price=trade.tradePrice,
            symbol=trade.symbol,
            transaction_type=TransactionType[trade.buySell],
        )

    @staticmethod
    def __filter_canceled_trades(
        trades: list[ibflex.Trade], cancels: list[ibflex.Trade]
    ) -> Iterable[ibflex.Trade]:
        canceled_order_ids = list(map(lambda x: x.origOrderID, cancels))
        non_canceled_trades = filter(
            lambda x: x.ibOrderID not in canceled_order_ids, trades
        )
        canceled_trades = filter(lambda x: x.ibOrderID in canceled_order_ids, trades)
        buy_after_cancel_trades: list[ibflex.Trade] = []
        for cancel in cancels:
            try:
                buy_after_cancel_trades.append(
                    next(
                        filter(
                            lambda x: x.transactionID == cancel.origTransactionID,
                            canceled_trades,
                        )
                    )
                )
            except StopIteration:
                continue

        return chain(non_canceled_trades, buy_after_cancel_trades)
