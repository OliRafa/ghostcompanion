import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import final

import requests

_BASE_URL = "https://coins.llama.fi"
# How far from the moment asked a price may be: DefiLlama's points are seconds
# apart for recent years, but some minutes apart for older ones.
_SEARCH_WIDTH = timedelta(hours=1)
_RETRIED_STATUSES = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 4
_TIMEOUT = 30


class DefiLlamaException(Exception):
    ...


@final
class DefiLlamaApi:
    """DefiLlama's coin prices, keyless. Coins are named the way DefiLlama names
    them: `<chain>:<contract>` for a token, the zero address for a chain's own
    coin, or `coingecko:<id>`."""

    def __init__(self, base_url: str = _BASE_URL):
        self._base_url = base_url
        self._session = requests.Session()

    def get_price(self, coin: str, moment: datetime) -> Decimal | None:
        """Returns the coin's USD price at the point DefiLlama has closest to
        `moment`, or None when it has none within an hour of it."""
        timestamp = int(moment.timestamp())
        url = f"{self._base_url}/prices/historical/{timestamp}/{coin}"
        # DefiLlama takes a width in candle notation, and refuses seconds.
        params = {"searchWidth": f"{int(_SEARCH_WIDTH.total_seconds() // 60)}m"}
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = self._session.get(url, params=params, timeout=_TIMEOUT)
            except requests.RequestException as error:
                raise DefiLlamaException(f"{coin}: {type(error).__name__}") from None
            if (
                response.status_code not in _RETRIED_STATUSES
                or attempt == _MAX_ATTEMPTS
            ):
                break
            time.sleep(2**attempt)

        if response.status_code != 200:
            raise DefiLlamaException(
                f"{coin}: HTTP {response.status_code} {response.text[:300]}"
            )

        point = response.json()["coins"].get(coin)
        if point is None:
            return None
        distance = abs(int(point["timestamp"]) - timestamp)
        if distance > _SEARCH_WIDTH.total_seconds():
            return None
        return Decimal(str(point["price"]))
