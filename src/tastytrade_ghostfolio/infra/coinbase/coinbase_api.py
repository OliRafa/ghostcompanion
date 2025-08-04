import secrets
import time
from typing import Any

import jwt
import requests
from cryptography.hazmat.primitives import serialization

from tastytrade_ghostfolio.configs.settings import CoinbaseSettings
from tastytrade_ghostfolio.core.ports.coinbase import CoinbasePort


class CoinbaseApi(CoinbasePort):
    def __init__(self) -> None:
        self.COINBASE_API_URL = "api.coinbase.com"

    def get_accounts(self) -> list[dict[str, Any]]:
        resource = "v2/accounts"
        uri = self._generate_uri(resource)
        jwt = self._generate_jwt(uri)
        self._accounts = self._request_data(resource, jwt)
        return self._accounts

    def get_transactions(self, coin: str) -> list[dict[str, Any]]:
        account_id = self._get_account_id(coin)
        resource = f"v2/accounts/{account_id}/transactions"
        uri = self._generate_uri(resource)
        jwt = self._generate_jwt(uri)
        return self._request_data(resource, jwt)

    def _generate_uri(self, resource: str, method: str = "GET") -> str:
        return f"{method} {self.COINBASE_API_URL}/{resource}"

    def _generate_jwt(self, uri: str) -> str:
        private_key = serialization.load_pem_private_key(
            CoinbaseSettings.SECRET.encode("utf-8"), password=None
        )

        jwt_payload = {
            "sub": CoinbaseSettings.API_KEY,
            "iss": "cdp",
            "nbf": int(time.time()),
            "exp": int(time.time()) + 120,
            "uri": uri,
        }

        return jwt.encode(
            jwt_payload,
            private_key,
            algorithm="ES256",
            headers={"kid": CoinbaseSettings.API_KEY, "nonce": secrets.token_hex()},
        )

    def _issue_request(self, url: str, headers: dict[str, str]) -> requests.Response:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response

    def _request_data(self, resource: str, jwt: str) -> list[dict[str, Any]]:
        url = f"https://{self.COINBASE_API_URL}/{resource}"
        headers = {"Authorization": f"Bearer {jwt}"}

        response = self._issue_request(url, headers)
        parsed_response = response.json()
        data: list[dict[str, Any]] = parsed_response.get("data")
        pagination = parsed_response.get("pagination")

        while pagination.get("next_uri"):
            url = f"https://{self.COINBASE_API_URL}/{pagination.get('next_uri')}"
            response = self._issue_request(url, headers)
            parsed_response = response.json()
            data += parsed_response.get("data")
            pagination = parsed_response.get("pagination")

        return data

    def _get_account_id(self, coin: str) -> str:
        try:
            account = next(
                filter(lambda x: x["currency"]["code"] == coin, self._accounts)
            )
            return account["id"]

        except StopIteration:
            return ""
