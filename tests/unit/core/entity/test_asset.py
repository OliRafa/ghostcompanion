import datetime
from decimal import Decimal

import pytest
from pytest import fixture

from tastytrade_ghostfolio.core.entity.asset import Asset
from tastytrade_ghostfolio.core.entity.dividend_info import DividendInfo
from tastytrade_ghostfolio.core.entity.split import Split
from tastytrade_ghostfolio.core.entity.trade import Trade
from tastytrade_ghostfolio.core.entity.transaction_type import TransactionType
from tastytrade_ghostfolio.core.exceptions import TradeNotFoundException


class AssetFactory:
    @fixture
    def dividend_info(self) -> DividendInfo:
        return DividendInfo(
            asset="STOCKA",
            ex_dividend_date=datetime.date(2023, 11, 28),
            unit_price=Decimal("12.5"),
        )

    @fixture
    def dividend(self) -> Trade:
        return Trade(
            executed_at=datetime.datetime(
                2023, 11, 30, 0, tzinfo=datetime.timezone.utc
            ),
            fee=Decimal("0.0"),
            symbol="STOCKA",
            transaction_type=TransactionType.DIVIDEND,
            unit_price=Decimal("0.0"),
            value=Decimal("25.0"),
        )

    @fixture
    def dividend_tax(self) -> Trade:
        return Trade(
            executed_at=datetime.datetime(
                2023, 11, 30, 0, tzinfo=datetime.timezone.utc
            ),
            fee=Decimal("8.333"),
            symbol="STOCKA",
            transaction_type=TransactionType.FEE,
            unit_price=Decimal("0.0"),
        )

    @fixture
    def trade(self) -> Trade:
        return Trade(
            executed_at=datetime.datetime(
                2023, 9, 27, 18, 36, 20, 28000, tzinfo=datetime.timezone.utc
            ),
            fee=Decimal("0.001"),
            quantity=Decimal("1.0"),
            symbol="STOCKA",
            transaction_type=TransactionType.BUY,
            unit_price=Decimal("40.3989"),
        )

    @fixture(autouse=True)
    def asset(self, trade):
        self.asset: Asset = Asset(symbol="STOCKA")
        self.asset.add_trades([trade])


class TestSplitShares(AssetFactory):
    @fixture
    def split(self) -> Split:
        return Split(
            effective_date=datetime.datetime(2023, 9, 28), ratio=2, symbol="STOCKA"
        )

    def should_split_before_effective_date(self, split):
        self.asset.split_shares(split)

        assert self.asset.trades[0].quantity == Decimal("2.0")

    def should_divide_unit_price(self, split):
        self.asset.split_shares(split)

        assert self.asset.trades[0].unit_price == Decimal("20.19945")

    def should_not_change_symbol_after_effective_date(self, split):
        after_the_fact_trade = self.asset.trades[0].model_copy()
        after_the_fact_trade.executed_at = datetime.datetime(
            2023, 10, 1, tzinfo=datetime.timezone.utc
        )
        self.asset.add_trades([after_the_fact_trade.model_copy()])

        self.asset.split_shares(split)

        assert self.asset.trades[1] == after_the_fact_trade


class TestHasTrade(AssetFactory):
    def should_return_true_when_trade_exists(self, trade):
        result = self.asset.has_trade(trade)

        assert result is True

    def should_return_false_when_trade_doesnt_exist(self):
        trade = Trade(
            executed_at=datetime.datetime(
                2023, 9, 30, 18, 36, 20, 28000, tzinfo=datetime.timezone.utc
            ),
            fee=Decimal("0.001"),
            quantity=Decimal("1.0"),
            symbol="STOCKA",
            transaction_type=TransactionType.BUY,
            unit_price=Decimal("40.3989"),
        )

        result = self.asset.has_trade(trade)

        assert result is False

    def should_return_true_when_dividend_trade_exists(self, dividend, dividend_info):
        self.asset.add_dividends([dividend], [dividend_info])

        result = self.asset.has_trade(dividend)

        assert result is True


class TestGetTrade(AssetFactory):
    def should_return_trade(self, trade: Trade):
        result = self.asset.get_trade(
            trade.executed_at, trade.quantity, trade.symbol, trade.unit_price
        )

        assert result == trade

    def when_given_dividend_should_return_it(self, dividend, dividend_info):
        self.asset.add_dividends([dividend], [dividend_info])

        result = self.asset.get_trade(
            dividend.executed_at,
            dividend.quantity,
            dividend.symbol,
            dividend.unit_price,
        )

        assert result.transaction_type == TransactionType.DIVIDEND

    def when_trade_isnt_found_should_raise_exception(self):
        with pytest.raises(TradeNotFoundException):
            self.asset.get_trade(
                datetime.datetime.now(), Decimal("0.0"), "NOTASYMBOL", Decimal("0.0")
            )


class TestDeleteTrade(AssetFactory):
    def should_delete_trade(self, trade):
        self.asset.delete_trade(trade)

        results = self.asset.trades

        assert not results

    def when_given_dividend_should_delete_it(self, dividend, dividend_info):
        self.asset.add_dividends([dividend], [dividend_info])
        self.asset.delete_trade(dividend)

        results = self.asset.dividends

        assert not results


class TestChangeSymbol(AssetFactory):
    def should_change_asset_symbol(self):
        self.asset.change_symbol("NEWSTOCKA")

        assert self.asset.symbol == "NEWSTOCKA"

    def should_change_symbol_for_all_trades(self):
        self.asset.change_symbol("NEWSTOCKA")

        results = self.asset.trades

        assert all(trade.symbol == "NEWSTOCKA" for trade in results)


class TestAddDividends(AssetFactory):
    def when_adding_dividend_should_add_tax_as_fee(
        self, dividend, dividend_tax, dividend_info
    ):
        inputs = [dividend, dividend_tax]

        self.asset.add_dividends(inputs, [dividend_info])
        results = self.asset.dividends

        assert len(results) == 1
        assert results[0].transaction_type == TransactionType.DIVIDEND
        assert results[0].fee == dividend_tax.fee

    def when_dividends_doesnt_have_tax_attached_result_should_be_0(
        self, dividend: Trade, dividend_tax, dividend_info: DividendInfo
    ):
        new_dividend = dividend.model_copy()
        new_dividend.executed_at += datetime.timedelta(days=31)

        new_dividend_info = dividend_info.model_copy()
        new_dividend_info.ex_dividend_date += datetime.timedelta(days=31)

        dividends = [dividend, dividend_tax, new_dividend]
        dividend_infos = [dividend_info, new_dividend_info]

        self.asset.add_dividends(dividends, dividend_infos)
        results = self.asset.dividends

        assert len(results) == 2
        assert all(
            result.transaction_type == TransactionType.DIVIDEND for result in results
        )
        assert any(result.fee == Decimal("0.0") for result in results)

    def should_calculate_quantity(
        self, dividend: Trade, trade: Trade, dividend_info: DividendInfo
    ):
        second_trade_before_dividends = trade.model_copy()
        second_trade_before_dividends.executed_at -= datetime.timedelta(days=2)

        trade_after_dividends = trade.model_copy()
        trade_after_dividends.executed_at = dividend.executed_at + datetime.timedelta(
            days=2
        )
        self.asset.add_trades([second_trade_before_dividends, trade_after_dividends])

        self.asset.add_dividends([dividend], [dividend_info])
        result = self.asset.dividends[0]

        assert (
            result.quantity == trade.quantity + second_trade_before_dividends.quantity
        )
        assert result.unit_price == Decimal("12.5")

    def when_theres_dividend_reinvestment_should_add_to_trades(
        self, dividend: Trade, dividend_info: DividendInfo
    ):
        reinvestment = Trade(
            executed_at=dividend.executed_at,
            fee=Decimal("0.001"),
            quantity=Decimal("0.58"),
            symbol=dividend.symbol,
            transaction_type=TransactionType.BUY,
            unit_price=dividend.value,
        )

        trade_count_before_dividends = len(self.asset.trades)

        self.asset.add_dividends([dividend, reinvestment], [dividend_info])
        dividends = self.asset.dividends

        assert all(
            dividend.transaction_type == TransactionType.DIVIDEND
            for dividend in dividends
        )

        trades = self.asset.trades

        assert len(trades) == trade_count_before_dividends + 1
