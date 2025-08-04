from pytest import fixture

from tastytrade_ghostfolio.core.entity.account import GhostfolioAccount
from tastytrade_ghostfolio.core.entity.portfolio import Portfolio
from tastytrade_ghostfolio.core.entity.transaction_type import TransactionType
from tastytrade_ghostfolio.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from tests.infra.ghostfolio_api import InMemoryGhostfolioApi


@fixture
def account_id() -> str:
    return "2a7efb1f-8f3c-43de-8778-f8488f1719d3"


@fixture
def portfolio(
    account_id,
    stock_a_trades,
    stock_b_trades,
    stock_a_dividends,
    stock_a_dividend_infos,
) -> Portfolio:
    account = GhostfolioAccount(id=account_id, name="Tastytrade")
    portfolio = Portfolio(account)
    portfolio.add_asset("STOCKA", stock_a_trades)
    portfolio.add_asset("STOCKB", stock_b_trades)
    portfolio.add_dividends("STOCKA", stock_a_dividends, stock_a_dividend_infos)

    return portfolio


class GhostfolioAdapterFactory:
    @fixture(autouse=True)
    def initialize_ghostfolio_adapter(self):
        self.ghostfolio_api = InMemoryGhostfolioApi()
        self.ghostfolio_adapter: GhostfolioAdapter = GhostfolioAdapter(
            self.ghostfolio_api
        )


class TestGetOrCreateAccount(GhostfolioAdapterFactory):
    def when_account_exists_should_return_it(self, account_id):
        result = self.ghostfolio_adapter.get_or_create_account("Tastytrade")

        assert result.id == account_id

    def should_create_if_not_exist(self):
        result = self.ghostfolio_adapter.get_or_create_account("NewAccount")

        assert result.id is not None

        accounts = [account["name"] for account in self.ghostfolio_api.get_accounts()]
        assert "NewAccount" in accounts

    def should_create_account_with_provided_currency(self):
        account = self.ghostfolio_adapter.get_or_create_account("NewAccount", "EUR")

        assert account.currency == "EUR"

    def when_no_currency_is_given_should_create_account_with_usd_currency(self):
        account = self.ghostfolio_adapter.get_or_create_account("NewAccount")

        assert account.currency == "USD"


class TestGetOrdersBySymbol(GhostfolioAdapterFactory):
    def should_return_only_orders_for_given_symbol(self, account_id):
        results = self.ghostfolio_adapter.get_orders_by_symbol(account_id, "STOCKA")

        assert all(result.symbol == "STOCKA" for result in results)

    def when_orders_are_absent_should_return_empty_list(self, account_id):
        results = self.ghostfolio_adapter.get_orders_by_symbol(account_id, "NOTASTOCK")

        assert not results


class TestDeleteOrders(GhostfolioAdapterFactory):
    def should_delete_orders(self, account_id):
        orders = self.ghostfolio_adapter.get_orders_by_symbol(account_id, "STOCKA")

        self.ghostfolio_adapter.delete_orders(orders)

        orders = self.ghostfolio_adapter.get_orders_by_symbol(account_id, "STOCKA")
        assert not orders


class TestExportPortfolio(GhostfolioAdapterFactory):
    def should_export_all_trades_in_portfolio(self, portfolio, stock_b_trades):
        self._cleanup_ghostfolio_trades(portfolio.account.id, ["STOCKA", "STOCKB"])

        self.ghostfolio_adapter.export_portfolio(portfolio)

        results = self.ghostfolio_adapter.get_orders_by_symbol(
            portfolio.account.id, "STOCKA"
        )

        assert any(result.transaction_type == TransactionType.BUY for result in results)

        results = self.ghostfolio_adapter.get_orders_by_symbol(
            portfolio.account.id, "STOCKB"
        )

        assert all(result.transaction_type == TransactionType.BUY for result in results)
        assert len(results) == len(stock_b_trades)

    def should_export_trades_in_correct_currency(self, account_id, stock_b_trades):
        account = GhostfolioAccount(id=account_id, name="Tastytrade")
        portfolio = Portfolio(account)
        for trade in stock_b_trades:
            trade.currency = "EUR"

        portfolio.add_asset("STOCKB", stock_b_trades)

        self._cleanup_ghostfolio_trades(portfolio.account.id, ["STOCKB"])

        self.ghostfolio_adapter.export_portfolio(portfolio)

        orders = self.ghostfolio_adapter.get_orders_by_symbol(account_id, "STOCKB")

        assert all(order.currency == "EUR" for order in orders)

    def should_export_all_dividends_in_portfolio(self, portfolio):
        self._cleanup_ghostfolio_trades(portfolio.account.id, ["STOCKA", "STOCKB"])

        self.ghostfolio_adapter.export_portfolio(portfolio)

        results = self.ghostfolio_adapter.get_orders_by_symbol(
            portfolio.account.id, "STOCKA"
        )

        assert any(
            result.transaction_type == TransactionType.DIVIDEND for result in results
        )

    def _cleanup_ghostfolio_trades(self, account_id: str, symbols: list[str]) -> None:
        for symbol in symbols:
            orders = self.ghostfolio_adapter.get_orders_by_symbol(account_id, symbol)
            self.ghostfolio_adapter.delete_orders(orders)
            orders = self.ghostfolio_adapter.get_orders_by_symbol(account_id, symbol)
            self.ghostfolio_adapter.delete_orders(orders)
