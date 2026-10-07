import pandas as pd
import yfinance


class YahooFinanceApi:
    def __init__(self):
        pass

    def get_dividends_by_ticker(self, ticker: str) -> pd.Series:
        return yfinance.Ticker(ticker).dividends

    def get_price_history(self, ticker: str) -> pd.Series:
        """Daily closes for the ticker's whole history (empty when it's unknown)."""
        history = yfinance.Ticker(ticker).history(
            period="max", interval="1d", auto_adjust=False
        )
        if history.empty:
            return pd.Series([], dtype="float64")

        return history["Close"]
