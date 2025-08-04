import datetime

from pytest import fixture

from ghostcompanion.core.entity.dividend_info import DividendInfo
from ghostcompanion.infra.dividends_provider.dividends_provider_adapter import (
    DividendsProviderAdapter,
)
from tests.infra.yahoo_finance_api import InMemoryYahooFinanceApi


class DividendsProviderAdapterFactory:
    @fixture(autouse=True)
    def dividends_provider(self):
        self.dividends_provider = DividendsProviderAdapter(InMemoryYahooFinanceApi())


class TestGetBySymbol(DividendsProviderAdapterFactory):
    def when_given_bound_dates_should_return_data_within_bounds(self):
        start_date = datetime.date(2020, 5, 28)
        end_date = datetime.date(2023, 9, 6)

        results: list[DividendInfo] = self.dividends_provider.get_by_symbol(
            "STOCKA", start_date, end_date
        )

        assert min(result.ex_dividend_date for result in results) >= start_date
        assert max(result.ex_dividend_date for result in results) <= end_date
        assert len(results) == 15

    def when_symbol_isnt_found_should_return_empty_list(self):
        start_date = datetime.date(2020, 5, 28)
        end_date = datetime.date(2023, 9, 6)

        results: list[DividendInfo] = self.dividends_provider.get_by_symbol(
            "STOCKB", start_date, end_date
        )

        assert results == []

    def when_no_dates_are_given_should_return_all_data(self):
        results: list[DividendInfo] = self.dividends_provider.get_by_symbol("STOCKA")

        assert len(results) == 28
