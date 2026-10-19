import time
from typing import Any, Literal, final

import requests

from ghostcompanion.configs.settings import EvmSettings
from ghostcompanion.core.entity.wallet import Network
from ghostcompanion.core.ports.evm_chain import EvmChainPort

_SUBDOMAINS = {Network.ETHEREUM: "eth-mainnet", Network.BASE: "base-mainnet"}
_CATEGORIES = ["external", "internal", "erc20"]
_PAGE_SIZE = "0x3e8"
_RECEIPTS_PER_BATCH = 50
_MAX_ATTEMPTS = 6
_TIMEOUT = 60


class AlchemyException(Exception):
    ...


@final
class AlchemyApi(EvmChainPort):
    def __init__(
        self,
        api_key: str | None = None,
        url_template: str = "https://{subdomain}.g.alchemy.com/v2/{api_key}",
    ):
        self._api_key = api_key if api_key is not None else EvmSettings.ALCHEMY_API_KEY
        self._url_template = url_template
        self._session = requests.Session()

    def get_asset_transfers(
        self, network: Network, address: str, direction: Literal["from", "to"]
    ) -> list[dict[str, Any]]:
        transfers: list[dict[str, Any]] = []
        params: dict[str, Any] = {
            "fromBlock": "0x0",
            "toBlock": "latest",
            f"{direction}Address": address,
            "category": _CATEGORIES,
            "withMetadata": True,
            # Zero-value transfers are kept: a call sending nothing still pays
            # a network fee, and this is how the wallet's own calls are found.
            "excludeZeroValue": False,
            "maxCount": _PAGE_SIZE,
        }
        while True:
            [result] = self._call(network, [("alchemy_getAssetTransfers", [params])])
            transfers += result["transfers"]
            if not result.get("pageKey"):
                return transfers
            params = {**params, "pageKey": result["pageKey"]}

    def get_transaction_receipts(
        self, network: Network, transaction_hashes: list[str]
    ) -> list[dict[str, Any]]:
        receipts = []
        for start in range(0, len(transaction_hashes), _RECEIPTS_PER_BATCH):
            batch = transaction_hashes[start : start + _RECEIPTS_PER_BATCH]
            receipts += self._call(
                network,
                [
                    ("eth_getTransactionReceipt", [transaction_hash])
                    for transaction_hash in batch
                ],
            )
        return receipts

    def _call(self, network: Network, calls: list[tuple[str, list[Any]]]) -> list[Any]:
        payload = [
            {"jsonrpc": "2.0", "id": index, "method": method, "params": params}
            for index, (method, params) in enumerate(calls)
        ]
        url = self._url_template.format(
            subdomain=_SUBDOMAINS[network], api_key=self._api_key
        )
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                response = self._session.post(url, json=payload, timeout=_TIMEOUT)
            except requests.RequestException as error:
                # The key is part of the URL, which requests puts in its errors.
                raise AlchemyException(
                    f"{network.value}: {type(error).__name__}"
                ) from None
            if response.status_code != 429 or attempt == _MAX_ATTEMPTS:
                break
            time.sleep(2**attempt)

        if response.status_code != 200:
            raise AlchemyException(
                f"{network.value}: HTTP {response.status_code}"
                f" {self._redact(response.text)[:300]}"
            )

        answers = {answer["id"]: answer for answer in response.json()}
        results = []
        for index, (method, _) in enumerate(calls):
            answer = answers[index]
            if "error" in answer:
                raise AlchemyException(
                    f"{network.value} {method}: {self._redact(str(answer['error']))}"
                )
            results.append(answer["result"])
        return results

    def _redact(self, text: str) -> str:
        return text.replace(self._api_key, "***") if self._api_key else text
