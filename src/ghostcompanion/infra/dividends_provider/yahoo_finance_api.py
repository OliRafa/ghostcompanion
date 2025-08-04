import pandas as pd
import yfinance


class YahooFinanceApi:
    def __init__(self):
        pass

    def get_dividends_by_ticker(self, ticker: str) -> pd.Series:
        return yfinance.Ticker(ticker).dividends
