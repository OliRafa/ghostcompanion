import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import final

from ghostcompanion.core.entity.binance import BinanceRecord

# Binance has named the time column both ways; either way it's UTC.
_TIME_COLUMNS = ("Time", "UTC_Time")
_COLUMNS = ("Account", "Operation", "Coin", "Change", "Remark")
_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class InvalidBinanceExportException(Exception):
    ...


@final
class BinanceTransactionRecords:
    """Reads the Transaction Records exports in a folder, one CSV per period, as
    Binance limits how much one export covers."""

    def __init__(self, folder: Path):
        self.folder = folder

    def get_records(self) -> list[BinanceRecord]:
        if not self.folder.is_dir():
            raise InvalidBinanceExportException(
                f"Binance history folder `{self.folder}` doesn't exist"
            )
        files = sorted(self.folder.glob("*.csv"))
        if not files:
            raise InvalidBinanceExportException(
                f"No Binance exports (*.csv) in `{self.folder}`"
            )

        exports = [(path, self._read(path)) for path in files]
        self._ensure_no_overlap(exports)
        records = [record for _, rows in exports for record in rows]
        return sorted(records, key=lambda x: x.executed_at)

    @staticmethod
    def _read(path: Path) -> list[BinanceRecord]:
        with path.open(encoding="utf-8-sig", newline="") as buffer:
            reader = csv.DictReader(buffer)
            columns = reader.fieldnames or []
            time_column = next((x for x in _TIME_COLUMNS if x in columns), None)
            missing = [x for x in _COLUMNS if x not in columns]
            if time_column is None or missing:
                raise InvalidBinanceExportException(
                    f"`{path}` isn't a Transaction Records export: it lacks"
                    f" {missing or list(_TIME_COLUMNS)}"
                )

            try:
                return [
                    BinanceRecord(
                        account=row["Account"],
                        change=Decimal(row["Change"]),
                        coin=row["Coin"],
                        executed_at=datetime.strptime(
                            row[time_column], _TIME_FORMAT
                        ).replace(tzinfo=timezone.utc),
                        operation=row["Operation"],
                        remark=row["Remark"] or "",
                    )
                    for row in reader
                ]
            except (InvalidOperation, ValueError) as error:
                raise InvalidBinanceExportException(
                    f"`{path}` line {reader.line_num}: {error}"
                ) from error

    @staticmethod
    def _ensure_no_overlap(exports: list[tuple[Path, list[BinanceRecord]]]):
        # Records carry no id, and a trade's fills can repeat the same change in
        # the same second, so overlapping exports can't be told from real
        # repeats.
        periods = sorted(
            (min(x.executed_at for x in rows), max(x.executed_at for x in rows), path)
            for path, rows in exports
            if rows
        )
        for (_, end, path), (start, _, next_path) in zip(periods, periods[1:]):
            if start <= end:
                raise InvalidBinanceExportException(
                    f"Binance exports `{path.name}` and `{next_path.name}` cover"
                    " overlapping periods; export each period once"
                )
