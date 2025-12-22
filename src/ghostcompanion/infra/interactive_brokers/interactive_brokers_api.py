from typing import final, override

from ibflex import AssetClass, FlexStatement, Trade, client, parser

from ghostcompanion.configs.settings import InteractiveBrokersSettings
from ghostcompanion.core.ports.interactive_brokers import InteractiveBrokersPort


@final
class InteractiveBrokersApi(InteractiveBrokersPort):
    def __init__(self) -> None:
        self.__account_statement = self.__get_account_statement()

    def __get_account_statement(self) -> FlexStatement:
        response = client.download(
            InteractiveBrokersSettings.TOKEN, InteractiveBrokersSettings.QUERY
        )
        flex_query = parser.parse(response)
        return flex_query.FlexStatements[0]

    @override
    def get_symbols(self) -> list[str]:
        stock_trades = filter(
            lambda x: x.assetCategory == AssetClass.STOCK,
            self.__account_statement.Trades,
        )
        return list(set(filter(None, map(lambda x: x.symbol, stock_trades))))

    @override
    def get_trades_by_symbol(self, symbol: str) -> list[Trade]:
        return list(
            filter(lambda x: x.symbol == symbol, self.__account_statement.Trades)
        )
