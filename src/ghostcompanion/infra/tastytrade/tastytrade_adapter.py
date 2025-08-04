from decimal import Decimal
from itertools import batched
from typing import Iterable

from tastytrade.account import Transaction

from ghostcompanion.core.entity.split import Split
from ghostcompanion.core.entity.symbol_change import SymbolChange
from ghostcompanion.core.entity.trade import Trade
from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.exceptions import TransactionTypeNotFoundException
from ghostcompanion.core.ports.tastytrade import TastytradePort
from ghostcompanion.infra.tastytrade.tastytrade_api import TastytradeApi


class TastytradeAdapter(TastytradePort):
    def __init__(self, tastytrade_api: TastytradeApi):
        self._tastytrade_api = tastytrade_api
        self._history = self._get_transaction_history()

    def _get_transaction_history(self) -> list[Transaction]:
        return self._tastytrade_api.get_trades_history()

    def get_trades(self, asset: str | None = None) -> list[Trade]:
        transactions = self._filter_trades(asset)
        return list(map(self._adapt_trade, transactions))

    def _adapt_trade_type(self, transaction: Transaction) -> TransactionType:
        match transaction.action:
            case "Buy to Open":
                return TransactionType.BUY
            case "Sell to Close":
                return TransactionType.SELL
            case None:
                if transaction.transaction_sub_type == "Dividend":
                    if transaction.value < 0:
                        return TransactionType.FEE

                    return TransactionType.DIVIDEND

                raise TransactionTypeNotFoundException(transaction)

            case _:
                raise TransactionTypeNotFoundException(transaction)

    def _adapt_trade(self, transaction: Transaction) -> Trade:
        transaction_type = self._adapt_trade_type(transaction)
        match transaction_type:
            case TransactionType.FEE:
                fee = abs(transaction.value)
            case _:
                fee = TastytradeAdapter._calculate_total_fee(
                    transaction.clearing_fees,
                    transaction.commission,
                    transaction.proprietary_index_option_fees,
                    transaction.regulatory_fees,
                )

        unit_price = Decimal("0.0") if transaction.price is None else transaction.price

        return Trade(
            description=transaction.description,
            executed_at=transaction.executed_at,
            fee=fee,
            quantity=transaction.quantity,
            symbol=transaction.symbol,
            transaction_type=transaction_type,
            unit_price=unit_price,
            value=transaction.value,
        )

    @staticmethod
    def _calculate_total_fee(
        clearing_fee: Decimal | None,
        commission: Decimal | None,
        proprietary_index_option_fees: Decimal | None,
        regulatory_fee: Decimal | None,
    ) -> Decimal:
        clearing_fee = Decimal("0.0") if clearing_fee is None else clearing_fee
        commission = Decimal("0.0") if commission is None else commission
        proprietary_index_option_fees = (
            Decimal("0.0")
            if proprietary_index_option_fees is None
            else proprietary_index_option_fees
        )
        regulatory_fee = Decimal("0.0") if regulatory_fee is None else regulatory_fee

        return abs(
            clearing_fee + commission + proprietary_index_option_fees + regulatory_fee
        )

    def _filter_trades(self, asset: str | None = None) -> Iterable[Transaction]:
        transactions = filter(lambda x: x.transaction_type == "Trade", self._history)
        if asset:
            return filter(lambda x: x.symbol == asset, transactions)

        return transactions

    def get_assets(self) -> list[str]:
        trades = self.get_trades()
        trades = set(map(lambda x: x.symbol, trades))

        dividends = self.get_dividends()
        dividends = set(map(lambda x: x.symbol, dividends))

        return list(trades | dividends)

    def get_symbol_changes(self) -> list[SymbolChange]:
        transactions = self._filter_symbol_changes()
        transactions = sorted(transactions, key=lambda x: x.transaction_date)

        symbol_changes = []
        for changes in batched(transactions, 2):
            old_symbol = next(filter(lambda x: x.action == "Sell to Close", changes))
            new_symbol = next(filter(lambda x: x.action == "Buy to Open", changes))
            symbol_changes.append(
                SymbolChange(old_symbol=old_symbol.symbol, new_symbol=new_symbol.symbol)
            )

        return symbol_changes

    def _filter_symbol_changes(self) -> Iterable[Transaction]:
        return filter(
            lambda x: x.transaction_type == "Receive Deliver"
            and x.transaction_sub_type == "Symbol Change",
            self._history,
        )

    def get_splits(self) -> list[Split]:
        transactions = self._filter_splits()
        transactions = sorted(transactions, key=lambda x: x.transaction_date)

        splits = []
        for split_specifications in batched(transactions, 2):
            sell_transaction = next(
                filter(lambda x: x.action == "Sell to Close", split_specifications)
            )
            buy_transaction = next(
                filter(lambda x: x.action == "Buy to Open", split_specifications)
            )

            split_ratio = buy_transaction.quantity / sell_transaction.quantity

            splits.append(
                Split(
                    effective_date=buy_transaction.transaction_date,
                    ratio=split_ratio,
                    symbol=buy_transaction.symbol,
                )
            )

        return splits

    def _filter_splits(self) -> Iterable[Transaction]:
        return filter(
            lambda x: x.transaction_type == "Receive Deliver"
            and x.transaction_sub_type == "Forward Split",
            self._history,
        )

    def get_dividends(self, asset: str | None = None) -> list[Trade]:
        dividends = self._filter_received_dividends(asset)
        dividends = list(map(self._adapt_trade, dividends))

        reinvestments = self._filter_dividend_reinvestments(asset)
        reinvestments = list(map(self._adapt_trade, reinvestments))

        return dividends + reinvestments

    def _filter_dividend_reinvestments(
        self, asset: str | None = None
    ) -> Iterable[Transaction]:
        transactions = filter(
            lambda x: x.transaction_type == "Receive Deliver"
            and x.transaction_sub_type == "Dividend",
            self._history,
        )

        if asset:
            return filter(lambda x: x.symbol == asset, transactions)

        return transactions

    def _filter_received_dividends(
        self, asset: str | None = None
    ) -> Iterable[Transaction]:
        transactions = filter(
            lambda x: x.transaction_type == "Money Movement"
            and x.transaction_sub_type == "Dividend",
            self._history,
        )

        if asset:
            return filter(lambda x: x.symbol == asset, transactions)

        return transactions
