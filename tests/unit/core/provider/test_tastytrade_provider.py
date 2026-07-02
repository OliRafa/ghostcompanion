import datetime
from decimal import Decimal

from pytest import fixture

from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.provider.tastytrade import TastytradeProvider
from tests.infra.tastytrade_api import (
    InMemoryTastytradeApi,
    InMemoryTastytradeApiWithDividendOnlyAsset,
    InMemoryTastytradeApiWithExtraTransaction,
)


class TastytradeProviderFactory:
    @fixture(autouse=True, scope="function")
    def tastytrade_provider(self) -> None:
        self.tastytrade_provider = TastytradeProvider(InMemoryTastytradeApi())


class TestTotalFee(TastytradeProviderFactory):
    def should_return_a_positive_number(self):
        result = TastytradeProvider._calculate_total_fee(
            Decimal("-0.001"), Decimal("-0.4"), Decimal("-0.03"), Decimal("0.0")
        )
        assert result == Decimal("0.431")

    def should_aggregate_fees(self):
        result = TastytradeProvider._calculate_total_fee(
            Decimal("-0.001"), Decimal("0.0"), Decimal("0.0"), Decimal("0.0")
        )
        assert result > Decimal("0.0")

    def when_any_fee_isnt_given_should_assume_zero(self):
        result = TastytradeProvider._calculate_total_fee(None, None, None, None)
        assert result == Decimal("0.0")


class TestGetTrades(TastytradeProviderFactory):
    def when_given_asset_should_return_trades_for_requested_asset_only(self):
        results = self.tastytrade_provider.get_trades("STOCKA")

        assert len(results) == 1
        assert results[0].symbol == "STOCKA"

    def when_no_asset_is_given_should_return_all_trades(self):
        results = self.tastytrade_provider.get_trades()

        assert len(results) == 3
        assert any(trade.symbol == "STOCKA" for trade in results)
        assert any(trade.symbol == "STOCKB" for trade in results)
        assert any(trade.symbol == "STOCKBB" for trade in results)


class TestGetAssets(TastytradeProviderFactory):
    def should_return_all_assets(self):
        results = self.tastytrade_provider.get_assets()

        assert len(results) == 3

    def when_theres_additional_history_entries_should_return_only_existing_assets(self):
        """Only assets with trades or dividends are returned, ignoring others."""
        provider = TastytradeProvider(InMemoryTastytradeApiWithExtraTransaction())
        results = provider.get_assets()

        assert all(asset is not None for asset in results)
        assert len(results) == 3  # Should still be 3, not 4

    def when_after_symbol_change_theres_no_new_trade_should_add_dividends(self):
        """Assets with only dividends (no trades) should be included in assets list"""
        provider = TastytradeProvider(InMemoryTastytradeApiWithDividendOnlyAsset())
        results = provider.get_assets()

        assert "STOCKC" in results
        assert len(results) == 4  # Original 3 + STOCKC


class TestGetSymbolChanges(TastytradeProviderFactory):
    def should_return_all_symbol_changes(self):
        results = self.tastytrade_provider.get_symbol_changes()

        assert len(results) == 1
        assert results[0].old_symbol == "STOCKB"
        assert results[0].new_symbol == "STOCKBB"


class TestGetSplits(TastytradeProviderFactory):
    def should_return_forward_and_reverse_splits(self):
        results = self.tastytrade_provider.get_splits()

        assert len(results) == 2

    def should_return_forward_split(self):
        results = self.tastytrade_provider.get_splits()

        forward_split = next(filter(lambda split: split.ratio > 1, results))

        assert forward_split.symbol == "STOCKA"
        assert forward_split.ratio == Decimal("2.0")
        assert forward_split.effective_date == datetime.date(2023, 9, 28)

    def should_return_reverse_split(self):
        results = self.tastytrade_provider.get_splits()

        reverse_split = next(filter(lambda split: split.ratio < 1, results))

        assert reverse_split.symbol == "STOCKA"
        assert reverse_split.ratio == Decimal("0.25")
        assert reverse_split.effective_date == datetime.date(2024, 3, 15)


class TestGetDividends(TastytradeProviderFactory):
    def should_return_dividend_reinvestments(self):
        results = self.tastytrade_provider.get_dividends("STOCKA")

        assert any(
            transaction.transaction_type == TransactionType.BUY
            for transaction in results
        )

    def when_dividend_is_taxed_should_return_trade_as_fee(self):
        results = self.tastytrade_provider.get_dividends("STOCKA")

        assert any(
            transaction.transaction_type == TransactionType.FEE
            for transaction in results
        )

        tax = next(filter(lambda x: x.transaction_type == TransactionType.FEE, results))

        assert tax.fee > Decimal("0.0")

    def should_return_received_dividends(self):
        results = self.tastytrade_provider.get_dividends("STOCKA")

        assert any(
            transaction.transaction_type == TransactionType.DIVIDEND
            for transaction in results
        )

        dividend = next(
            filter(lambda x: x.transaction_type == TransactionType.DIVIDEND, results)
        )

        assert dividend.value > Decimal("0.0")
