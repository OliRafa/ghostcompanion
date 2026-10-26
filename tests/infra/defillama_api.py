from datetime import datetime, timedelta
from decimal import Decimal

from ghostcompanion.infra.defillama.defillama_api import DefiLlamaException
from tests.resources.defillama.prices import PRICE_POINTS

_SEARCH_WIDTH = timedelta(hours=1)


class InMemoryDefiLlamaApi:
    def __init__(self, price_points: dict[str, dict[str, float]] | None = None):
        self._price_points = PRICE_POINTS if price_points is None else price_points
        self.unreachable = False
        self.requests: list[tuple[str, datetime]] = []

    def get_price(self, coin: str, moment: datetime) -> Decimal | None:
        self.requests.append((coin, moment))
        if self.unreachable:
            raise DefiLlamaException(f"{coin}: ConnectionError")

        points = {
            datetime.fromisoformat(at): price
            for at, price in self._price_points.get(coin, {}).items()
        }
        closest = min(points, key=lambda at: abs(at - moment), default=None)
        if closest is None or abs(closest - moment) > _SEARCH_WIDTH:
            return None
        return Decimal(str(points[closest]))
