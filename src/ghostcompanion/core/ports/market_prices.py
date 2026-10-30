import datetime
from abc import ABC, abstractmethod
from decimal import Decimal

from ghostcompanion.core.entity.wallet import Network


class MarketPricePort(ABC):
    @abstractmethod
    def get_crypto_price(
        self,
        symbol: str,
        currency: str,
        moment: datetime.datetime,
        network: Network | None,
        contract: str | None = None,
    ) -> Decimal:
        """Returns the coin's price at `moment`. The coin is the one at `contract`
        on `network`, or the network's own coin without one; `symbol` names it
        on Yahoo, whose daily close on that day (or the closest day before) is
        used when there's no price for the moment itself. A coin known only by
        its symbol, as an exchange lists it, has no `network` and only that
        close."""
        ...
