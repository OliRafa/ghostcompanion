from tastytrade import Account, Session
from tastytrade.account import Transaction

from ghostcompanion.configs.settings import Settings


class TastytradeApi:
    def __init__(self):
        self._session = self._get_session()
        self._account = self._get_account()

    def _get_session(self) -> Session:
        return Session(Settings.Tastytrade.USERNAME, Settings.Tastytrade.PASSWORD)

    def _get_account(self) -> Account:
        return Account.get_accounts(self._session)[0]

    def get_trades_history(self) -> list[Transaction]:
        return self._account.get_history(self._session)
