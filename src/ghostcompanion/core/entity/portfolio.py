from collections.abc import Iterable
from typing import final

from ghostcompanion.core.entity.account import GhostfolioAccount
from ghostcompanion.core.entity.asset import Asset
from ghostcompanion.core.entity.dividend_info import DividendInfo
from ghostcompanion.core.entity.split import Split
from ghostcompanion.core.entity.symbol_change import SymbolChange
from ghostcompanion.core.entity.trade import Trade
from ghostcompanion.core.exceptions import AssetNotFoundException


@final
class Portfolio:
    def __init__(self, account: GhostfolioAccount):
        self.account = account
        self._assets: list[Asset] = []

    def add_asset(self, symbol: str, trades: list[Trade]):
        asset = Asset(symbol=symbol)
        asset.add_trades(trades)
        self._assets.append(asset)

    def adapt_symbol_changes(self, changes: list[SymbolChange]):
        for change in changes:
            if self.has_asset(change.old_symbol):
                old_asset = self.get_asset(change.old_symbol)

                try:
                    new_asset = self.get_asset(change.new_symbol)
                    old_asset.change_symbol(change.new_symbol)
                    new_asset.add_trades(old_asset.trades)
                    self._assets.remove(old_asset)

                except AssetNotFoundException:
                    old_asset.change_symbol(change.new_symbol)

    def has_asset(self, symbol: str) -> bool:
        for asset in self._assets:
            if asset.symbol == symbol:
                return True

        return False

    def get_asset(self, symbol: str) -> Asset:
        try:
            return next(filter(lambda x: x.symbol == symbol, self._assets))

        except StopIteration:
            raise AssetNotFoundException()

    def adapt_stock_splits(self, splits: list[Split]):
        for split in splits:
            asset = self.get_asset(split.symbol)
            asset.split_shares(split)

    def get_symbols(self) -> list[str]:
        return [asset.symbol for asset in self._assets]

    def get_trades(self, asset: str) -> list[Trade]:
        asset: Asset = self.get_asset(asset)
        return asset.trades

    def get_absent_trades(self, asset: str, trades: Iterable[Trade]) -> list[Trade]:
        try:
            asset: Asset = self.get_asset(asset)
            return [trade for trade in trades if not asset.has_trade(trade)]

        except StopIteration:
            raise AssetNotFoundException()

    def delete_repeated_trades(self, asset: str, trades: Iterable[Trade]):
        asset: Asset = self.get_asset(asset)
        for trade in trades:
            asset.delete_trade(trade)

        if not asset.trades and not asset.dividends:
            self._assets.remove(asset)

    def add_dividends(
        self,
        asset: str,
        dividends: list[Trade],
        dividend_infos: list[DividendInfo] | None = None,
    ):
        asset: Asset = self.get_asset(asset)
        asset.add_dividends(dividends, dividend_infos)

    def get_dividends(self, asset: str) -> list[Trade]:
        asset: Asset = self.get_asset(asset)
        return asset.dividends

    def get_oldest_trade(self, asset: str) -> Trade:
        try:
            asset: Asset = self.get_asset(asset)
            return asset.get_oldest_trade()

        except StopIteration:
            raise AssetNotFoundException()
