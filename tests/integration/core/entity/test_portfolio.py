import datetime
from decimal import Decimal

import pytest
from pytest import fixture

from tastytrade_ghostfolio.core.entity.asset import Asset
from tastytrade_ghostfolio.core.entity.portfolio import Portfolio
from tastytrade_ghostfolio.core.entity.symbol_change import SymbolChange
from tastytrade_ghostfolio.core.entity.trade import Trade
from tastytrade_ghostfolio.core.entity.transaction_type import TransactionType
from tastytrade_ghostfolio.core.exceptions import AssetNotFoundException
from tests.conftest import mark_test


class PortfolioFactory:
    @fixture(autouse=True)
    def portfolio(self, stock_a_trades, stock_b_trades):
        self.portfolio: Portfolio = Portfolio()
        self.portfolio.add_asset("STOCKA", stock_a_trades)
        self.portfolio.add_asset("STOCKB", stock_b_trades)


class TestGetSymbols(PortfolioFactory):
    @mark_test
    def should_return_all_symbols(self):
        results = self.portfolio.get_symbols()

        assert len(results) == 2
        assert "STOCKA" in results
        assert "STOCKB" in results


class TestAdaptSymbolChanges(PortfolioFactory):
    @fixture
    def change(self) -> SymbolChange:
        return SymbolChange(old_symbol="STOCKA", new_symbol="NEWSTOCKA")

    @mark_test
    def when_new_symbol_doesnt_exist_yet_should_create_new_asset(
        self, change: SymbolChange
    ):
        self.portfolio.adapt_symbol_changes([change])

        results = self.portfolio.get_symbols()

        assert change.new_symbol in results

    @mark_test
    def after_changing_symbol_should_delete_old_asset(self, change: SymbolChange):
        self.portfolio.adapt_symbol_changes([change])

        results = self.portfolio.get_symbols()

        assert change.old_symbol not in results

    @mark_test
    def when_changing_symbols_all_trades_must_have_new_symbol(
        self, change: SymbolChange
    ):
        self.portfolio.adapt_symbol_changes([change])
        results = self.portfolio.get_trades(change.new_symbol)

        assert all(trade.symbol == change.new_symbol for trade in results)

    @mark_test
    def when_new_symbol_already_exists_should_merge_assets(
        self, stock_a_trades, stock_b_trades
    ):
        change = SymbolChange(old_symbol="STOCKA", new_symbol="STOCKB")

        self.portfolio.adapt_symbol_changes([change])
        results = self.portfolio.get_trades(change.new_symbol)

        assert len(results) == len(stock_a_trades) + len(stock_b_trades)
        assert all(trade.symbol == change.new_symbol for trade in results)


class TestGetAsset(PortfolioFactory):
    @mark_test
    def when_asset_is_absent_should_raise_exception(self):
        with pytest.raises(AssetNotFoundException):
            self.portfolio.get_asset("NOTASSET")

    @mark_test
    def should_return_asset(self):
        result = self.portfolio.get_asset("STOCKA")

        assert isinstance(result, Asset)


class TestGetAbsentTrades(PortfolioFactory):
    @mark_test
    def should_return_trades_for_asset_only(self):
        trades = self.portfolio.get_absent_trades("STOCKA", [])

        assert all(trade.symbol == "STOCKA" for trade in trades)

    @mark_test
    def when_asset_is_not_found_should_raise_exception(self):
        with pytest.raises(AssetNotFoundException):
            self.portfolio.get_absent_trades("NOTASTOCK", [])

    @mark_test
    def should_return_trades_not_present_in_portfolio(self):
        abset_trade = Trade(
            executed_at=datetime.datetime(
                2023, 9, 30, 18, 36, 20, 28000, tzinfo=datetime.timezone.utc
            ),
            fee=Decimal("0.001"),
            quantity=Decimal("3.0"),
            symbol="STOCKA",
            transaction_type=TransactionType.BUY,
            unit_price=Decimal("42.3989"),
        )

        results = self.portfolio.get_absent_trades("STOCKA", [abset_trade])

        assert len(results) == 1
        assert results[0] == abset_trade

    @mark_test
    def should_return_dividends_not_present_in_portfolio(
        self, stock_a_dividends, stock_a_dividend_infos
    ):
        absent_dividend = Trade(
            executed_at=datetime.datetime(
                2023, 9, 30, 18, 36, 20, 28000, tzinfo=datetime.timezone.utc
            ),
            fee=Decimal("0.001"),
            quantity=Decimal("3.0"),
            symbol="STOCKA",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("5.0"),
        )
        self.portfolio.add_dividends(
            "STOCKA", stock_a_dividends, stock_a_dividend_infos
        )
        dividends = self.portfolio.get_dividends("STOCKA")

        results = self.portfolio.get_absent_trades(
            "STOCKA", [*dividends, absent_dividend]
        )

        assert len(results) == 1
        assert results[0] == absent_dividend


class TestGetTrades(PortfolioFactory):
    @mark_test
    def should_return_trades_for_given_asset(self):
        results = self.portfolio.get_trades("STOCKA")

        assert all(trade.symbol == "STOCKA" for trade in results)


class TestDeleteRepeatedOrders(PortfolioFactory):
    @mark_test
    def when_all_orders_from_symbol_are_repeated_should_remove_symbol_from_portfolio(
        self, stock_a_trades
    ):
        self.portfolio.delete_repeated_trades("STOCKA", stock_a_trades)

        symbols = self.portfolio.get_symbols()

        assert "STOCKA" not in symbols

    @mark_test
    def when_theres_no_trades_but_theres_dividends_should_not_remove_symbol(
        self, stock_a_trades, stock_a_dividends, stock_a_dividend_infos
    ):
        stock_a_dividends = list(
            filter(
                lambda x: x.transaction_type == TransactionType.DIVIDEND,
                stock_a_dividends,
            )
        )
        self.portfolio.add_dividends(
            "STOCKA", stock_a_dividends, stock_a_dividend_infos
        )

        self.portfolio.delete_repeated_trades("STOCKA", stock_a_trades)
        symbols = self.portfolio.get_symbols()

        assert "STOCKA" in symbols

    @mark_test
    def should_delete_repeated_trades(self, stock_a_trades):
        repeated_trades = stock_a_trades[1:]

        self.portfolio.delete_repeated_trades("STOCKA", repeated_trades)

        results = self.portfolio.get_trades("STOCKA")

        assert results == [stock_a_trades[0]]

    @mark_test
    def should_delete_repeated_dividends(
        self, stock_a_dividends, stock_a_dividend_infos
    ):
        stock_a_dividends = list(
            filter(
                lambda x: x.transaction_type == TransactionType.DIVIDEND,
                stock_a_dividends,
            )
        )
        self.portfolio.add_dividends(
            "STOCKA", stock_a_dividends, stock_a_dividend_infos
        )
        dividends = self.portfolio.get_dividends("STOCKA")

        self.portfolio.delete_repeated_trades("STOCKA", dividends)
        results = self.portfolio.get_dividends("STOCKA")

        assert not results


class TestAddDividends(PortfolioFactory):
    @mark_test
    def should_add_dividends(self, stock_a_dividends, stock_a_dividend_infos):
        self.portfolio.add_dividends(
            "STOCKA", stock_a_dividends, stock_a_dividend_infos
        )

        results = self.portfolio.get_dividends("STOCKA")

        assert len(results) > 0
