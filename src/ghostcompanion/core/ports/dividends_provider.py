import datetime
from abc import ABC, abstractmethod

from ghostcompanion.core.entity.dividend_info import DividendInfo


class DividendsProviderPort(ABC):
    @abstractmethod
    def get_by_symbol(
        self, symbol: str, start_date: datetime.date, end_date: datetime.date
    ) -> list[DividendInfo | None]: ...
