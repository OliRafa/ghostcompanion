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

    def provider_having_sold_btc_for_usdt(self) -> BinanceProvider:
        return self.provider_with(
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

    def when_a_coin_was_traded_since_should_book_its_trades(self):
        provider = self.provider_having_sold_btc_for_usdt()

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

    def should_value_a_swap_by_its_stablecoin_side_over_bitcoin(self):
        provider = self.provider_having_sold_btc_for_usdt()

        swap = [
            x
            for x in provider.get_movements()
            if x.transaction_id == "binance-order-9001"
        ]

        assert [(x.symbol, x.market_unit_price) for x in swap] == [
            ("BTC", None),
            ("USDT", Decimal("1.0002")),
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


def convert(
    order_id: int,
    moment: str,
    given: tuple[str, str],
    got: tuple[str, str],
    status: str = "SUCCESS",
) -> dict:
    return {
        "orderId": order_id,
        "orderStatus": status,
        "fromAsset": given[0],
        "fromAmount": given[1],
        "toAsset": got[0],
        "toAmount": got[1],
        "createTime": milliseconds(moment),
    }


class TestConvertsSinceExports(BinanceProviderFactory):
    @fixture(autouse=True)
    def converted_into_usdc(self, initialize_provider):
        balances = {**BALANCES, "BRL": Decimal("825.37"), "USDC": Decimal("59.87")}
        del balances["XVG"]
        self.provider = self.provider_with(
            balances=balances,
            converts=[
                convert(7000, "2022-08-01 12:00:00", ("LTC", "1"), ("USDC", "52")),
                convert(
                    7001, "2025-06-14 09:12:05", ("XVG", "11988"), ("USDC", "41.5")
                ),
                convert(7002, "2025-06-14 09:15:40", ("BRL", "100"), ("USDC", "18.37")),
                convert(
                    7003,
                    "2025-06-14 09:17:00",
                    ("BTC", "0.01"),
                    ("USDC", "650"),
                    "FAIL",
                ),
            ],
        )

    def should_ask_for_converts_from_where_the_exports_end(self):
        self.provider.get_trades()

        assert self.api.converts_since == at("2022-09-15 06:30:00")

    def should_swap_coins_converted_into_each_other(self):
        swap = [
            x
            for x in self.provider.get_movements()
            if x.transaction_id == "binance-convert-7001"
        ]

        assert [(x.symbol, x.quantity, x.market_unit_price) for x in swap] == [
            ("XVG", Decimal("-11988"), None),
            ("USDC", Decimal("41.5"), Decimal("0.9998")),
        ]
        assert swap[0].executed_at == at("2025-06-14 09:12:05")

    def should_buy_with_fiat_what_was_converted_from_it(self):
        [buy] = [x for x in self.provider.get_trades() if x.symbol == "USDC"]

        assert buy.transaction_type == TransactionType.BUY
        assert buy.currency == "BRL"
        assert buy.quantity == Decimal("18.37")
        assert buy.value == Decimal("100")

    def should_skip_converts_that_failed_or_the_exports_have(self):
        references = {x.transaction_id for x in self.provider.get_movements()}

        assert "binance-convert-7000" not in references
        assert "binance-convert-7003" not in references

    def when_converts_explain_the_balances_should_not_scan_or_warn(self, caplog):
        with caplog.at_level(logging.WARNING):
            self.provider.get_trades()

        assert self.api.scanned == []
        assert caplog.text == ""


def dust(
    conversion_id: int,
    moment: str,
    given: tuple[str, str],
    transferred: tuple[str, str],
    charge: str,
) -> dict:
    return {
        "transId": conversion_id,
        "operateTime": milliseconds(moment),
        "fromAsset": given[0],
        "amount": given[1],
        "targetAsset": transferred[0],
        "transferedAmount": transferred[1],
        "serviceChargeAmount": charge,
    }


class TestDustConversionsSinceExports(BinanceProviderFactory):
    @fixture(autouse=True)
    def swept_into_usdc(self, initialize_provider):
        legacy = dust(8002, "2025-07-01 00:00:00", ("XNO", "0.5"), ("", "0.0012"), "0")
        del legacy["targetAsset"]
        self.provider = self.provider_with(
            balances={
                **BALANCES,
                "BNB": Decimal("0.0012"),
                "BTC": Decimal("0.07372187"),
                "LTC": Decimal("0.218"),
                "USDC": Decimal("0.80458"),
                "XNO": Decimal("39.5"),
            },
            dust_conversions=[
                dust(8000, "2022-01-10 00:00:00", ("XLM", "1"), ("BNB", "0.0004"), "0"),
                dust(
                    8001,
                    "2025-06-20 14:00:00",
                    ("BTC", "0.00001"),
                    ("USDC", "0.8"),
                    "0.016",
                ),
                dust(
                    8001,
                    "2025-06-20 14:00:00",
                    ("LTC", "0.0003"),
                    ("USDC", "0.021"),
                    "0.00042",
                ),
                legacy,
            ],
        )

    def should_swap_each_coin_swept_for_the_coin_it_became(self):
        movements = [
            (x.transaction_id, x.symbol, x.quantity, x.market_unit_price)
            for x in self.provider.get_movements()
            if x.transaction_id.startswith("binance-dust-8001")
        ]

        assert movements == [
            ("binance-dust-8001-btc", "BTC", Decimal("-0.00001"), None),
            ("binance-dust-8001-btc", "USDC", Decimal("0.8"), Decimal("0.9998")),
            ("binance-dust-8001-ltc", "LTC", Decimal("-0.0003"), None),
            ("binance-dust-8001-ltc", "USDC", Decimal("0.021"), Decimal("0.9998")),
        ]

    def should_sell_the_charge_out_of_what_was_transferred_for_nothing(self):
        charges = [
            (x.symbol, x.quantity)
            for x in self.provider.get_trades()
            if x.description == "Trading fee" and x.executed_at.year == 2025
        ]

        assert charges == [("USDC", Decimal("0.016")), ("USDC", Decimal("0.00042"))]

    def when_record_names_no_target_should_have_become_bnb(self):
        movements = [
            (x.symbol, x.quantity)
            for x in self.provider.get_movements()
            if x.transaction_id == "binance-dust-8002-xno"
        ]

        assert movements == [("XNO", Decimal("-0.5")), ("BNB", Decimal("0.0012"))]

    def should_skip_dust_conversions_the_exports_have(self):
        references = {x.transaction_id for x in self.provider.get_movements()}

        assert "binance-dust-8000-xlm" not in references

    def when_dust_conversions_explain_the_balances_should_not_scan_or_warn(
        self, caplog
    ):
        with caplog.at_level(logging.WARNING):
            self.provider.get_trades()

        assert self.api.scanned == []
        assert caplog.text == ""


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
