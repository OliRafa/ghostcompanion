from abc import ABC, abstractmethod

from tastytrade_ghostfolio.core.entity.account import GhostfolioAccount
from tastytrade_ghostfolio.core.entity.portfolio import Portfolio
from tastytrade_ghostfolio.core.entity.trade import Trade


class GhostfolioPort(ABC):
    @abstractmethod
    def get_or_create_account(self, name: str) -> GhostfolioAccount: ...

    @abstractmethod
    def get_orders_by_symbol(self, account_id: str, symbol: str) -> list[Trade]: ...

    @abstractmethod
    def delete_orders(self, orders: list[Trade]): ...

    @abstractmethod
    def export_portfolio(self, portfolio: Portfolio): ...
