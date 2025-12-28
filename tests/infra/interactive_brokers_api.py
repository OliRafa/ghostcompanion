from typing import final, override

from ibflex import AssetClass, Trade

from ghostcompanion.core.ports.interactive_brokers import InteractiveBrokersPort
from tests.resources.interactive_brokers import TRADES


@final
class InMemoryInteractiveBrokersApi(InteractiveBrokersPort):
    def __init__(self, trades: list[Trade] = TRADES) -> None:
        self.__trades = trades

    @override
    def get_symbols(self) -> list[str]:
        stock_trades = filter(
            lambda x: x.assetCategory == AssetClass.STOCK, self.__trades
        )
        return list(set(filter(None, map(lambda x: x.symbol, stock_trades))))

    @override
    def get_trades_by_symbol(self, symbol: str) -> list[Trade]:
        return list(filter(lambda x: x.symbol == symbol, self.__trades))
