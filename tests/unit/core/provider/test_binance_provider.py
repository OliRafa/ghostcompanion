import logging
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path

from pytest import fixture

from ghostcompanion.core.entity.binance import BinanceRecord
from ghostcompanion.core.entity.transaction_type import TransactionType
from ghostcompanion.core.provider.binance import BinanceProvider
from ghostcompanion.infra.market_prices.market_price_adapter import MarketPriceAdapter
from ghostcompanion.repositories.binance_transaction_records import (
    BinanceTransactionRecords,
)
from tests.infra.binance_api import InMemoryBinanceApi
from tests.infra.yahoo_finance_api import InMemoryYahooFinanceApi
from tests.resources.binance.api import (
    BALANCES,
    LTC_DEPOSIT_HASH,
    PRICE_HISTORIES,
    XLM_WITHDRAWAL_HASH,
    milliseconds,
)

RECORDS = BinanceTransactionRecords(Path("tests/resources/binance")).get_records()


def at(moment: str) -> datetime:
    return datetime.fromisoformat(moment).replace(tzinfo=timezone.utc)


def trade(symbol: str, order_id: int, moment: str, **fields: str | bool) -> dict:
    return {
        "symbol": symbol,
        "id": order_id * 10,
        "orderId": order_id,
        "time": milliseconds(moment),
        "isMaker": False,
        "isBestMatch": True,
        **fields,
    }


class BinanceProviderFactory:
    @fixture(autouse=True)
    def initialize_provider(self):
        self.market_prices = MarketPriceAdapter(
            InMemoryYahooFinanceApi(PRICE_HISTORIES)
        )
        self.api = InMemoryBinanceApi()
        self.provider = BinanceProvider(self.api, self.market_prices, RECORDS)

    def provider_with(
        self, records: list[BinanceRecord] | None = RECORDS, **api_records
    ) -> BinanceProvider:
        self.api = InMemoryBinanceApi(**api_records)
        return BinanceProvider(self.api, self.market_prices, records)


class TestGetTrades(BinanceProviderFactory):
    def should_buy_with_fiat_at_what_was_paid_its_fills_together(self):
        [buy] = [
            x
            for x in self.provider.get_trades()
            if x.executed_at.date() == date(2021, 3, 9)
            and x.transaction_type == TransactionType.BUY
        ]

        assert (buy.symbol, buy.currency) == ("BTC", "BRL")
        assert buy.quantity == Decimal("0.0057")
        assert buy.value == Decimal("1574.63")
        assert buy.fee == Decimal("0")

    def should_sell_for_fiat_with_its_fee(self):
        [sell] = [
            x
            for x in self.provider.get_trades()
            if x.currency == "EUR" and x.transaction_type == TransactionType.SELL
        ]

        assert sell.symbol == "BTC"
        assert sell.quantity == Decimal("0.009")
        assert sell.value == Decimal("512.37")
        assert sell.fee == Decimal("0.51237")

    def should_sell_a_fee_in_a_coin_for_nothing_a_second_later(self):
        fees = [x for x in self.provider.get_trades() if x.description == "Trading fee"]
        [fee] = [x for x in fees if x.executed_at.date() == date(2021, 3, 9)]

        assert fee.symbol == "BTC"
        assert fee.transaction_type == TransactionType.SELL
        assert fee.quantity == Decimal("0.0000057")
        assert fee.unit_price == Decimal("0")
        assert fee.executed_at == at("2021-03-09 11:41:54")

    def should_not_book_a_fee_in_fiat_as_a_trade(self):
        fees = [x for x in self.provider.get_trades() if x.description == "Trading fee"]

        assert {x.symbol for x in fees} == {"BTC", "XVG", "XLM"}

    def should_buy_airdrops_for_nothing(self):
        [airdrop] = [x for x in self.provider.get_trades() if x.symbol == "ETHW"]

        assert airdrop.transaction_type == TransactionType.BUY
        assert airdrop.quantity == Decimal("0.12345678")
        assert airdrop.unit_price == Decimal("0")
        assert airdrop.description == "Airdrop"

    def when_coin_was_renamed_should_book_it_under_its_new_name_only(self):
        symbols = {x.symbol for x in self.provider.get_trades()}
        symbols |= {x.symbol for x in self.provider.get_movements()}

        assert "NANO" not in symbols
        assert not [x for x in self.provider.get_trades() if x.symbol == "XNO"]


class TestGetMovements(BinanceProviderFactory):
    def should_swap_coins_valued_by_their_bitcoin_side(self):
        movements = [
            x
            for x in self.provider.get_movements()
            if x.executed_at == at("2019-02-03 10:05:17")
        ]

        assert [(x.symbol, x.quantity, x.market_unit_price) for x in movements] == [
            ("LTC", Decimal("-2.5"), None),
            ("BTC", Decimal("0.081234"), Decimal("3480.0")),
        ]
        assert len({x.transaction_id for x in movements}) == 1

    def should_swap_a_renamed_coin_under_its_new_name(self):
        movements = [
            x
            for x in self.provider.get_movements()
            if x.executed_at == at("2019-06-11 08:00:39")
        ]

        assert [(x.symbol, x.quantity) for x in movements] == [
            ("XNO", Decimal("-100")),
            ("BTC", Decimal("0.0152")),
        ]

    def should_book_deposits_from_the_api_with_their_transaction_ids(self):
        [deposit] = [
            x
            for x in self.provider.get_movements()
            if x.transaction_id == LTC_DEPOSIT_HASH
        ]

        assert deposit.symbol == "LTC"
        assert deposit.quantity == Decimal("2.7183")
        assert deposit.market_unit_price == Decimal("33.21")
        assert deposit.account == "Binance"

    def should_book_withdrawals_from_the_api_with_their_fee(self):
        [withdrawal] = [x for x in self.provider.get_movements() if x.fee > 0]

        assert withdrawal.symbol == "XLM"
        assert withdrawal.quantity == Decimal("-299.99")
        assert withdrawal.fee == Decimal("0.01")
        assert withdrawal.transaction_id == XLM_WITHDRAWAL_HASH
        assert withdrawal.destination_address == "GEXAMPLEWITHDRAWALADDRESS"
        assert withdrawal.executed_at == at("2021-07-22 08:09:10")

    def should_skip_transfers_that_did_not_complete(self):
        transfers = [
            x
            for x in self.provider.get_movements()
            if not x.transaction_id.startswith("binance-")
        ]

        assert [x.symbol for x in transfers] == ["LTC", "XNO", "XLM"]


class TestTradesSinceExports(BinanceProviderFactory):
    def when_balances_are_what_the_exports_end_with_should_not_scan(self):
        self.provider.get_trades()

        assert self.api.scanned == []

    def when_a_coin_was_traded_since_should_book_its_trades(self):
        provider = self.provider_with(
            balances={
                **BALANCES,
                "BTC": Decimal("0.07273187"),
                "USDT": Decimal("25.4745"),
            },
            trades={
                "BTCUSDT": [
                    trade(
                        "BTCUSDT",
                        9001,
                        "2023-03-02 10:00:00",
                        price="25500",
                        qty="0.001",
                        quoteQty="25.5",
                        commission="0.0255",
                        commissionAsset="USDT",
                        isBuyer=False,
                    )
                ]
            },
        )

        swap = [
            x
            for x in provider.get_movements()
            if x.transaction_id == "binance-order-9001"
        ]
        fees = [x for x in provider.get_trades() if x.symbol == "USDT"]

        assert [(x.symbol, x.quantity) for x in swap] == [
            ("BTC", Decimal("-0.001")),
            ("USDT", Decimal("25.5")),
        ]
        assert [(x.quantity, x.description) for x in fees] == [
            (Decimal("0.0255"), "Trading fee")
        ]

    def should_find_trades_through_a_coin_no_longer_held(self):
        provider = self.provider_with(
            balances={
                **BALANCES,
                "BTC": Decimal("0.07173187"),
                "USDT": Decimal("38.92104"),
            },
            trades={
                "XRPBTC": [
                    trade(
                        "XRPBTC",
                        9002,
                        "2023-03-02 10:00:00",
                        price="0.00002",
                        qty="100",
                        quoteQty="0.002",
                        commission="0.1",
                        commissionAsset="XRP",
                        isBuyer=True,
                    )
                ],
                "XRPUSDT": [
                    trade(
                        "XRPUSDT",
                        9003,
                        "2023-03-03 10:00:00",
                        price="0.39",
                        qty="99.9",
                        quoteQty="38.96",
                        commission="0.03896",
                        commissionAsset="USDT",
                        isBuyer=False,
                    )
                ],
            },
        )

        references = {x.transaction_id for x in provider.get_movements()}

        assert {"binance-order-9002", "binance-order-9003"} <= references

    def when_balances_stay_unexplained_should_warn(self, caplog):
        provider = self.provider_with(balances={**BALANCES, "BTC": Decimal("0.5")})

        with caplog.at_level(logging.WARNING):
            provider.get_trades()

        assert "holds 0.5 BTC, but its records add up to 0.07373187" in caplog.text

    def when_there_are_no_exports_should_book_every_trade_the_api_has(self):
        provider = self.provider_with(
            None,
            balances={"BTC": Decimal("0.04"), "USDT": Decimal("229.77")},
            deposits=[
                {
                    "amount": "0.05",
                    "coin": "BTC",
                    "status": 1,
                    "txId": "5" * 64,
                    "insertTime": milliseconds("2023-01-05 12:00:00"),
                }
            ],
            withdrawals=[],
            fiat_deposits=[],
            fiat_withdrawals=[],
            trades={
                "BTCUSDT": [
                    trade(
                        "BTCUSDT",
                        9004,
                        "2023-03-02 10:00:00",
                        price="23000",
                        qty="0.01",
                        quoteQty="230",
                        commission="0.23",
                        commissionAsset="USDT",
                        isBuyer=False,
                    )
                ]
            },
        )

        references = {x.transaction_id for x in provider.get_movements()}

        assert "binance-order-9004" in references


class TestWarnings(BinanceProviderFactory):
    def when_api_transfers_differ_from_the_exports_should_warn(self, caplog):
        provider = self.provider_with(
            deposits=[x for x in self.api.get_deposits() if x["coin"] != "LTC"]
        )

        with caplog.at_level(logging.WARNING):
            provider.get_movements()

        assert "deposits and withdrawals of LTC" in caplog.text

    def when_exports_have_records_it_does_not_read_should_warn(self, caplog):
        provider = self.provider_with(
            RECORDS
            + [
                BinanceRecord(
                    account="Spot",
                    change=Decimal("-0.01"),
                    coin="BTC",
                    executed_at=at("2022-09-16 00:00:00"),
                    operation="Simple Earn Flexible Subscription",
                )
            ],
            balances={**BALANCES, "BTC": Decimal("0.07363187")},
        )

        with caplog.at_level(logging.WARNING):
            provider.get_trades()

        assert "1 `Simple Earn Flexible Subscription` record(s)" in caplog.text

    def when_two_pairs_trade_in_the_same_second_should_warn(self, caplog):
        moment = at("2022-09-16 00:00:00")
        records = [
            BinanceRecord(
                account="Spot",
                change=Decimal(change),
                coin=coin,
                executed_at=moment,
                operation=operation,
            )
            for operation, coin, change in (
                ("Buy", "ETH", "1"),
                ("Sell", "BTC", "-0.05"),
                ("Buy", "XRP", "100"),
                ("Sell", "USDT", "-40"),
            )
        ]
        provider = self.provider_with(records)

        with caplog.at_level(logging.WARNING):
            provider.get_trades()

        assert "1 `trade` record(s)" in caplog.text


class TestGetCurrentCashBalance(BinanceProviderFactory):
    def should_return_the_balance_in_the_currency(self):
        balance = self.provider.get_current_cash_balance("BRL")

        assert balance.amount == Decimal("925.37")
        assert balance.currency == "BRL"
        assert balance.date == date.today()

    def when_currency_is_not_held_should_return_zero(self):
        assert self.provider.get_current_cash_balance("USD").amount == Decimal("0")
