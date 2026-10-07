import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests
from pytest import fixture, raises

from ghostcompanion.infra.blockchain.mempool_space_api import MempoolSpaceApi

FIRST_PAGE = [{"txid": f"first-{i}"} for i in range(25)]
SECOND_PAGE = [{"txid": f"second-{i}"} for i in range(3)]


class FakeEsploraServer(BaseHTTPRequestHandler):
    """Serves a 28-transaction history in Esplora's 25-per-page chunks, plus an
    address that is rate-limited once and one that always fails."""

    rate_limited_once = False

    def do_GET(self):
        match self.path:
            case "/api/address/paged/txs/chain":
                self._reply(200, FIRST_PAGE)
            case "/api/address/paged/txs/chain/first-24":
                self._reply(200, SECOND_PAGE)
            case "/api/address/limited/txs/chain":
                if not FakeEsploraServer.rate_limited_once:
                    FakeEsploraServer.rate_limited_once = True
                    self._reply(429, "Too Many Requests", {"Retry-After": "0"})
                else:
                    self._reply(200, SECOND_PAGE)
            case _:
                self._reply(500, "boom")

    def _reply(self, status: int, body, headers: dict[str, str] | None = None):
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, *args):
        ...


class MempoolSpaceApiFactory:
    @fixture(autouse=True)
    def initialize_api(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeEsploraServer)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.api = MempoolSpaceApi(f"http://127.0.0.1:{server.server_port}/api/")
        yield
        server.shutdown()
        server.server_close()


class TestGetAddressTransactions(MempoolSpaceApiFactory):
    def should_follow_pages_until_the_last_one(self):
        transactions = self.api.get_address_transactions("paged")

        assert transactions == FIRST_PAGE + SECOND_PAGE

    def when_rate_limited_should_retry(self):
        transactions = self.api.get_address_transactions("limited")

        assert transactions == SECOND_PAGE

    def when_server_fails_should_raise_exception(self):
        with raises(requests.HTTPError):
            self.api.get_address_transactions("broken")
