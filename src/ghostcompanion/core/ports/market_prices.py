import datetime
from abc import ABC, abstractmethod
from decimal import Decimal


class MarketPricePort(ABC):
    @abstractmethod
    def get_crypto_price(
        self, symbol: str, currency: str, day: datetime.date
    ) -> Decimal:
        """Returns the coin's daily close on `day`, or on the closest day before."""
        ...
