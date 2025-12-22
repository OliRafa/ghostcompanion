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

        trades = filter(
            lambda x: x.buySell == ibflex.BuySell.BUY
            or x.buySell == ibflex.BuySell.SELL,
            trades,
        )

        return list(map(self.__adapt_trade, trades))

    def __adapt_trade(self, trade: ibflex.Trade) -> Trade:
        return Trade(
            currency=trade.currency,
            executed_at=trade.dateTime,
            fee=abs(trade.ibCommission) + abs(trade.taxes),
            quantity=abs(trade.quantity),
            unit_price=trade.tradePrice,
            symbol=trade.symbol,
            transaction_type=TransactionType[trade.buySell],
        )
