import pandas as pd
from pandas import Timestamp

from tests.resources.yahoo_finance.price_history import PRICE_HISTORIES


class InMemoryYahooFinanceApi:
    def __init__(
        self, price_histories: dict[str, tuple[str, dict[str, float]]] | None = None
    ):
        self._price_histories = (
            PRICE_HISTORIES if price_histories is None else price_histories
        )
        self._dividends = {
            Timestamp("2015-05-18 00:00:00-0400", tz="America/New_York"): 0.286,
            Timestamp("2015-09-09 00:00:00-0400", tz="America/New_York"): 0.62,
            Timestamp("2016-05-17 00:00:00-0400", tz="America/New_York"): 0.82,
            Timestamp("2016-09-20 00:00:00-0400", tz="America/New_York"): 0.55,
            Timestamp("2017-05-22 00:00:00-0400", tz="America/New_York"): 0.22,
            Timestamp("2017-09-25 00:00:00-0400", tz="America/New_York"): 0.06,
            Timestamp("2018-05-14 00:00:00-0400", tz="America/New_York"): 0.06,
            Timestamp("2018-09-26 00:00:00-0400", tz="America/New_York"): 0.06,
            Timestamp("2019-05-15 00:00:00-0400", tz="America/New_York"): 0.06,
            Timestamp("2019-09-26 00:00:00-0400", tz="America/New_York"): 0.06,
            Timestamp("2020-05-28 00:00:00-0400", tz="America/New_York"): 0.29,
            Timestamp("2020-06-15 00:00:00-0400", tz="America/New_York"): 0.81,
            Timestamp("2020-08-18 00:00:00-0400", tz="America/New_York"): 0.47,
            Timestamp("2020-11-19 00:00:00-0500", tz="America/New_York"): 0.09,
            Timestamp("2021-02-24 00:00:00-0500", tz="America/New_York"): 0.03,
            Timestamp("2021-05-20 00:00:00-0400", tz="America/New_York"): 0.03,
            Timestamp("2021-08-30 00:00:00-0400", tz="America/New_York"): 0.03,
            Timestamp("2021-11-22 00:00:00-0500", tz="America/New_York"): 0.03,
            Timestamp("2022-06-01 00:00:00-0400", tz="America/New_York"): 0.06,
            Timestamp("2022-08-30 00:00:00-0400", tz="America/New_York"): 0.03,
            Timestamp("2022-11-21 00:00:00-0500", tz="America/New_York"): 0.03,
            Timestamp("2023-02-21 00:00:00-0500", tz="America/New_York"): 0.03,
            Timestamp("2023-06-01 00:00:00-0400", tz="America/New_York"): 1.1,
            Timestamp("2023-06-08 00:00:00-0400", tz="America/New_York"): 0.7,
            Timestamp("2023-09-06 00:00:00-0400", tz="America/New_York"): 0.8,
            Timestamp("2023-12-12 00:00:00-0500", tz="America/New_York"): 0.57,
            Timestamp("2024-05-22 00:00:00-0400", tz="America/New_York"): 4.57,
            Timestamp("2024-07-09 00:00:00-0400", tz="America/New_York"): 1.15,
        }

    def get_dividends_by_ticker(self, ticker: str) -> pd.Series:
        if ticker == "STOCKA":
            return pd.Series(self._dividends)

        return pd.Series([])

    def get_price_history(self, ticker: str) -> pd.Series:
        timezone, closes = self._price_histories.get(ticker, ("UTC", {}))
        return pd.Series(
            list(closes.values()),
            index=pd.DatetimeIndex(list(closes)).tz_localize(timezone),
            dtype="float64",
        )
