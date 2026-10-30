from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from pytest import fixture, raises

from ghostcompanion.core.entity.binance import BinanceRecord
from ghostcompanion.repositories.binance_transaction_records import (
    BinanceTransactionRecords,
    InvalidBinanceExportException,
)

RESOURCES = Path("tests/resources/binance")
HEADER = "User ID,Time,Account,Operation,Coin,Change,Remark"


class BinanceTransactionRecordsFactory:
    @fixture(autouse=True)
    def initialize_folder(self, tmp_path: Path):
        self.folder = tmp_path

    def export(self, name: str, *lines: str, header: str = HEADER) -> None:
        self.folder.joinpath(name).write_text(
            "﻿" + "\r\n".join((header, *lines)) + "\r\n", encoding="utf-8"
        )

    def records(self) -> list[BinanceRecord]:
        return BinanceTransactionRecords(self.folder).get_records()


class TestGetRecords(BinanceTransactionRecordsFactory):
    def should_read_every_record_of_an_export(self):
        records = BinanceTransactionRecords(RESOURCES).get_records()

        assert len(records) == 30
        assert records[1] == BinanceRecord(
            account="Spot",
            change=Decimal("0.081234"),
            coin="BTC",
            executed_at=datetime(2019, 2, 3, 10, 5, 17, tzinfo=timezone.utc),
            operation="Buy",
        )

    def should_keep_remarks(self):
        records = BinanceTransactionRecords(RESOURCES).get_records()

        assert {x.remark for x in records} == {
            "",
            "Withdraw fee is included",
            "NANO to XNO",
        }

    def should_read_every_export_in_order(self):
        self.export("2021.csv", "1,2021-02-01 00:00:00,Spot,Deposit,BTC,0.2,")
        self.export("2020.csv", "1,2020-02-01 00:00:00,Spot,Deposit,BTC,0.1,")

        assert [x.change for x in self.records()] == [Decimal("0.1"), Decimal("0.2")]

    def when_time_column_is_named_utc_time_should_read_it(self):
        self.export(
            "export.csv",
            "1,2020-02-01 00:00:00,Spot,Deposit,BTC,0.1,",
            header="User_ID,UTC_Time,Account,Operation,Coin,Change,Remark",
        )

        [record] = self.records()

        assert record.executed_at == datetime(2020, 2, 1, tzinfo=timezone.utc)

    def when_exports_overlap_should_raise_exception(self):
        self.export(
            "a.csv",
            "1,2020-02-01 00:00:00,Spot,Deposit,BTC,0.1,",
            "1,2020-09-01 00:00:00,Spot,Deposit,BTC,0.1,",
        )
        self.export("b.csv", "1,2020-06-01 00:00:00,Spot,Deposit,BTC,0.1,")

        with raises(InvalidBinanceExportException, match="overlapping"):
            self.records()

    def when_an_export_is_empty_should_read_the_others(self):
        self.export("empty.csv")
        self.export("2020.csv", "1,2020-02-01 00:00:00,Spot,Deposit,BTC,0.1,")

        assert len(self.records()) == 1

    def when_a_column_is_missing_should_raise_exception(self):
        self.export(
            "trades.csv",
            "2020-02-01 00:00:00,BTCUSDT,BUY",
            header="Date(UTC),Pair,Side",
        )

        with raises(InvalidBinanceExportException, match="isn't a Transaction"):
            self.records()

    def when_a_change_is_not_a_number_should_raise_exception(self):
        self.export("export.csv", "1,2020-02-01 00:00:00,Spot,Deposit,BTC,lots,")

        with raises(InvalidBinanceExportException, match="line 2"):
            self.records()

    def when_folder_is_missing_should_raise_exception(self):
        with raises(InvalidBinanceExportException, match="doesn't exist"):
            BinanceTransactionRecords(self.folder.joinpath("nope")).get_records()

    def when_folder_has_no_exports_should_raise_exception(self):
        with raises(InvalidBinanceExportException, match="No Binance exports"):
            self.records()
