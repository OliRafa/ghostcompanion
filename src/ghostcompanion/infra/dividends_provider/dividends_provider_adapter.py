import datetime
from decimal import Decimal
from typing import Optional

from ghostcompanion.core.entity.dividend_info import DividendInfo
from ghostcompanion.core.ports.dividends_provider import DividendsProviderPort
from ghostcompanion.infra.dividends_provider.yahoo_finance_api import (
    YahooFinanceApi,
)


class DividendsProviderAdapter(DividendsProviderPort):
    def __init__(self, yahoo_finance_api: YahooFinanceApi):
        self.yahoo_finance_api = yahoo_finance_api

    def get_by_symbol(
        self,
        symbol: str,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
    ) -> list[DividendInfo | None]:
        dividends = self.yahoo_finance_api.get_dividends_by_ticker(symbol)
        if dividends.empty:
            return []

        if start_date and end_date:
            dividends = dividends[
                (dividends.index >= str(start_date))
                & (dividends.index <= str(end_date))
            ]

        dividend_infos = []
        for executed_at, value in dividends.items():
            dividend_infos.append(
                DividendInfo(
                    asset=symbol,
                    ex_dividend_date=executed_at.date(),
                    unit_price=Decimal(str(value)),
                )
            )

        return dividend_infos
