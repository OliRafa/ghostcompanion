from tastytrade import Account, Session
from tastytrade.account import Transaction

from ghostcompanion.configs.settings import Settings


class TastytradeApi:
    def __init__(self):
        self._session = self._get_session()
        self._account = self._get_account()

    def _get_session(self) -> Session:
        return Session(
            Settings.Tastytrade.CLIENT_SECRET, Settings.Tastytrade.REFRESH_TOKEN
        )

    def _get_account(self) -> Account:
        return Account.get(self._session)[0]

    def get_trades_history(self) -> list[Transaction]:
        # Tastytrade SDK currently has a pagination bug, where it won't get
        # transactions for other than the first page.
        # `per_page` here is just an arbitrary number to try to bypass this issue
        # while a proper fix is not in place.
        return self._account.get_history(self._session, per_page=1500)
