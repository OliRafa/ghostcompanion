import time
from typing import Any, final

import requests

from ghostcompanion.configs.settings import BlockchainSettings
from ghostcompanion.core.ports.blockchain import BlockchainPort

# Esplora pages confirmed transactions 25 at a time, newest first.
_PAGE_SIZE = 25
_MAX_ATTEMPTS = 5
_TIMEOUT = 30


@final
class MempoolSpaceApi(BlockchainPort):
    """Client for mempool.space, or any Esplora-compatible API (e.g. a self-hosted
    mempool or electrs instance, which keeps the queried addresses private)."""

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or BlockchainSettings.MEMPOOL_BASE_URL).rstrip("/")
        self._session = requests.Session()

    def get_address_transactions(self, address: str) -> list[dict[str, Any]]:
        transactions = self._get(f"/address/{address}/txs/chain")
        page = transactions
        while len(page) == _PAGE_SIZE:
            last_seen = page[-1]["txid"]
            page = self._get(f"/address/{address}/txs/chain/{last_seen}")
            transactions += page

        return transactions

    def _get(self, path: str) -> list[dict[str, Any]]:
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            response = self._session.get(f"{self.base_url}{path}", timeout=_TIMEOUT)
            if response.status_code != 429 or attempt == _MAX_ATTEMPTS:
                break

            # Public instances rate-limit bursts; one weekly run can afford to wait.
            time.sleep(float(response.headers.get("Retry-After", 2**attempt)))

        response.raise_for_status()
        return response.json()
