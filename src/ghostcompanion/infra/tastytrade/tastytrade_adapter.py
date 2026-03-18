from decimal import Decimal

from tastytrade.account import Transaction

from ghostcompanion.core.ports.tastytrade import TastytradePort
from ghostcompanion.infra.tastytrade.tastytrade_api import TastytradeApi


class TastytradeAdapter(TastytradePort):
    def __init__(self, tastytrade_api: TastytradeApi):
        self._tastytrade_api = tastytrade_api

    def get_trades_history(self) -> list[Transaction]:
        return self._tastytrade_api.get_trades_history()

    def get_current_cash_balance(self) -> Decimal:
        """Get the current cash balance from Tastytrade account."""
        return self._tastytrade_api.get_current_cash_balance()
