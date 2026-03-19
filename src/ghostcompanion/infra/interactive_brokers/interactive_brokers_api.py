from decimal import Decimal
from typing import final, override

from ibflex import (
    AssetClass,
    ChangeInDividendAccrual,
    FlexStatement,
    Trade,
    client,
    parser,
)

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
    def get_current_cash_balance(self) -> Decimal:
        """Get total ending cash from CashReport.

        Returns the total ending cash across all currencies.
        """
        if self.__account_statement.CashReport:
            return self.__account_statement.CashReport[0].endingCash or Decimal("0")
        return Decimal("0")

    @override
    def get_dividends_by_symbol(self, symbol: str) -> list[ChangeInDividendAccrual]:
        return list(
            filter(
                lambda x: x.symbol == symbol,
                self.__account_statement.ChangeInDividendAccruals,
            )
        )

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
