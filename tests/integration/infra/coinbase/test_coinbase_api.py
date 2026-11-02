import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from pytest import fixture

from ghostcompanion.configs.settings import CoinbaseSettings
from ghostcompanion.infra.coinbase.coinbase_api import CoinbaseApi


def account(id: str, code: str, name: str) -> dict:
    return {"id": id, "name": name, "currency": {"code": code}, "type": "wallet"}


def page(transaction_ids: list[str], next_uri: str | None = None) -> dict:
    return {
        "data": [{"id": x} for x in transaction_ids],
        "pagination": {"next_uri": next_uri},
    }


ADA_TRANSACTIONS = "/v2/accounts/ada-wallet/transactions"
RESPONSES = {
    # Coinbase lists a staked coin's account before the coin's own wallet.
    "/v2/accounts": {
        "data": [
            account("ada-staked", "ADA", "Staked ADA"),
            account("ada-wallet", "ADA", "ADA Wallet"),
            account("btc-wallet", "BTC", "BTC Wallet"),
        ],
        "pagination": {"next_uri": None},
    },
    "/v2/accounts/ada-staked/transactions": page(["stake-1"]),
    ADA_TRANSACTIONS: page(["buy-1"], f"{ADA_TRANSACTIONS}?starting_after=buy-1"),
    f"{ADA_TRANSACTIONS}?starting_after=buy-1": page(["buy-2"]),
    "/v2/accounts/btc-wallet/transactions": page(["btc-1"]),
}


class FakeCoinbase(BaseHTTPRequestHandler):
    requests: list[tuple[str, str]] = []

    def do_GET(self):
        token = self.headers["Authorization"].removeprefix("Bearer ")
        FakeCoinbase.requests.append((self.path, token))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(RESPONSES[self.path]).encode())

    def log_message(self, *args):
        ...


class CoinbaseApiFactory:
    @fixture(autouse=True)
    def initialize_api(self, monkeypatch):
        private_key = ec.generate_private_key(ec.SECP256R1())
        monkeypatch.setattr(CoinbaseSettings, "API_KEY", "organizations/test")
        monkeypatch.setattr(
            CoinbaseSettings,
            "SECRET",
            private_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            ).decode(),
        )
        FakeCoinbase.requests = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeCoinbase)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.api = CoinbaseApi(f"http://127.0.0.1:{server.server_port}")


class TestGetTransactions(CoinbaseApiFactory):
    def when_coin_has_several_accounts_should_read_all_of_them(self):
        transactions = self.api.get_transactions("ADA")

        assert [x["id"] for x in transactions] == ["stake-1", "buy-1", "buy-2"]

    def should_not_read_accounts_of_other_coins(self):
        self.api.get_transactions("ADA")

        assert not any("btc-wallet" in path for path, _ in FakeCoinbase.requests)

    def should_sign_each_account_for_its_own_path(self):
        self.api.get_transactions("ADA")

        host = urlparse(self.api.base_url).netloc
        uris = {
            path: jwt.decode(token, options={"verify_signature": False})["uri"]
            for path, token in FakeCoinbase.requests
        }
        assert uris["/v2/accounts/ada-staked/transactions"] == (
            f"GET {host}/v2/accounts/ada-staked/transactions"
        )
        assert uris[ADA_TRANSACTIONS] == f"GET {host}{ADA_TRANSACTIONS}"
