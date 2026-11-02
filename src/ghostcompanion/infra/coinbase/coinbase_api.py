import secrets
import time
from decimal import Decimal
from functools import cached_property
from typing import Any
from urllib.parse import urljoin, urlparse

import jwt
import requests
from cryptography.hazmat.primitives import serialization

from ghostcompanion.configs.settings import CoinbaseSettings
from ghostcompanion.core.ports.coinbase import CoinbasePort


class CoinbaseApi(CoinbasePort):
    def __init__(self, base_url: str = "https://api.coinbase.com") -> None:
        self.base_url = base_url

    def get_current_cash_balance(self, currency: str) -> Decimal:
        """Get cash balance for specific fiat currency.

        Returns the balance from fiat accounts matching the specified currency.
        Only includes accounts with type='fiat' and matching currency code.

        Args:
            currency: The currency code to filter by (e.g., 'USD', 'EUR')

        Returns:
            Decimal: Total balance across all matching fiat accounts
        """
        accounts = self.get_accounts()
        total_balance = Decimal("0")

        for account in accounts:
            # Must be fiat type
            if account.get("type") == "fiat":
                account_currency = account.get("currency", {}).get("code", "")
                # Must match requested currency
                if account_currency == currency:
                    balance = account.get("balance", {}).get("amount", "0")
                    total_balance += Decimal(balance)

        return total_balance

    def get_accounts(self) -> list[dict[str, Any]]:
        resource = "v2/accounts"
        uri = self._generate_uri(resource)
        jwt = self._generate_jwt(uri)
        return self._request_data(resource, jwt)

    def get_transactions(self, coin: str) -> list[dict[str, Any]]:
        """Every transaction of the coin, across the accounts holding it: staked
        coins are kept in an account of their own."""
        transactions = []
        for account in self._accounts:
            if account["currency"]["code"] == coin:
                resource = f"v2/accounts/{account['id']}/transactions"
                uri = self._generate_uri(resource)
                transactions += self._request_data(resource, self._generate_jwt(uri))

        return transactions

    @cached_property
    def _accounts(self) -> list[dict[str, Any]]:
        return self.get_accounts()

    def _generate_uri(self, resource: str, method: str = "GET") -> str:
        return f"{method} {urlparse(self.base_url).netloc}/{resource}"

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
        url = f"{self.base_url}/{resource}"
        headers = {"Authorization": f"Bearer {jwt}"}

        response = self._issue_request(url, headers)
        parsed_response = response.json()
        data: list[dict[str, Any]] = parsed_response.get("data")
        pagination = parsed_response.get("pagination")

        while pagination.get("next_uri"):
            url = urljoin(self.base_url, pagination.get("next_uri"))
            response = self._issue_request(url, headers)
            parsed_response = response.json()
            data += parsed_response.get("data")
            pagination = parsed_response.get("pagination")

        return data
