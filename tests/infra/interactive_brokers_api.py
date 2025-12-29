from typing import final, override

from ibflex import AssetClass, ChangeInDividendAccrual, Trade

from ghostcompanion.core.ports.interactive_brokers import InteractiveBrokersPort
from tests.resources.interactive_brokers import DIVIDENDS, TRADES


@final
class InMemoryInteractiveBrokersApi(InteractiveBrokersPort):
    def __init__(self, trades: list[Trade] = TRADES) -> None:
        self.__trades = trades
        self.__dividends = DIVIDENDS

    @override
    def get_dividends_by_symbol(self, symbol: str) -> list[ChangeInDividendAccrual]:
        return list(filter(lambda x: x.symbol == symbol, self.__dividends))

    @override
    def get_symbols(self) -> list[str]:
        stock_trades = filter(
            lambda x: x.assetCategory == AssetClass.STOCK, self.__trades
        )
        return list(set(filter(None, map(lambda x: x.symbol, stock_trades))))

    @override
    def get_trades_by_symbol(self, symbol: str) -> list[Trade]:
        return list(filter(lambda x: x.symbol == symbol, self.__trades))
