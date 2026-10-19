import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pytest import fixture, raises

from ghostcompanion.core.entity.wallet import Network
from ghostcompanion.infra.evm.alchemy_api import AlchemyApi, AlchemyException

API_KEY = "secret-api-key"


class FakeAlchemy(BaseHTTPRequestHandler):
    """Answers JSON-RPC batches like Alchemy: transfers in two pages for the
    `paged` address, an error for `erroring`, and one rate limit for `limited`."""

    requests: list[tuple[str, list[dict]]] = []
    rate_limited_once = False

    def do_POST(self):
        _, subdomain, api_key = self.path.split("/")
        calls = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeAlchemy.requests.append((subdomain, calls))
        if api_key != API_KEY:
            return self._reply(401, f"invalid key {api_key}")

        answers = []
        for call in calls:
            if call["method"] == "eth_getTransactionReceipt":
                result = {"transactionHash": call["params"][0]}
                answers.append({"jsonrpc": "2.0", "id": call["id"], "result": result})
                continue

            params = call["params"][0]
            address = params.get("fromAddress") or params.get("toAddress")
            if address == "limited" and not FakeAlchemy.rate_limited_once:
                FakeAlchemy.rate_limited_once = True
                return self._reply(429, "slow down")
            if address == "erroring":
                error = {"code": -32600, "message": f"bad request for {API_KEY}"}
                answers.append({"jsonrpc": "2.0", "id": call["id"], "error": error})
                continue
            if address == "paged" and "pageKey" not in params:
                result = {"transfers": [{"uniqueId": "first"}], "pageKey": "next"}
            else:
                result = {"transfers": [{"uniqueId": "last"}]}
            answers.append({"jsonrpc": "2.0", "id": call["id"], "result": result})
        self._reply(200, answers)

    def _reply(self, status: int, body):
        self.send_response(status)
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, *args):
        ...


class AlchemyApiFactory:
    @fixture(autouse=True)
    def initialize_api(self):
        FakeAlchemy.requests = []
        FakeAlchemy.rate_limited_once = False
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeAlchemy)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.url_template = (
            f"http://127.0.0.1:{server.server_port}/{{subdomain}}/{{api_key}}"
        )
        self.api = AlchemyApi(API_KEY, self.url_template)
        yield
        server.shutdown()
        server.server_close()


class TestGetAssetTransfers(AlchemyApiFactory):
    def should_follow_pages_until_the_last_one(self):
        transfers = self.api.get_asset_transfers(Network.BASE, "paged", "from")

        assert [transfer["uniqueId"] for transfer in transfers] == ["first", "last"]

    def should_ask_the_network_for_native_and_token_transfers(self):
        self.api.get_asset_transfers(Network.ETHEREUM, "0xwallet", "to")

        [(subdomain, [call])] = FakeAlchemy.requests
        params = call["params"][0]
        assert subdomain == "eth-mainnet"
        assert params["toAddress"] == "0xwallet"
        assert params["category"] == ["external", "internal", "erc20"]
        assert params["withMetadata"] is True

    def when_rate_limited_should_retry(self, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda _: None)

        transfers = self.api.get_asset_transfers(Network.BASE, "limited", "from")

        assert [transfer["uniqueId"] for transfer in transfers] == ["last"]


class TestGetTransactionReceipts(AlchemyApiFactory):
    def should_batch_the_requests(self):
        hashes = [f"0x{index:064x}" for index in range(120)]

        receipts = self.api.get_transaction_receipts(Network.BASE, hashes)

        assert [receipt["transactionHash"] for receipt in receipts] == hashes
        assert [len(calls) for _, calls in FakeAlchemy.requests] == [50, 50, 20]

    def when_no_hashes_are_given_should_ask_nothing(self):
        assert self.api.get_transaction_receipts(Network.BASE, []) == []
        assert FakeAlchemy.requests == []


class TestErrors(AlchemyApiFactory):
    def when_key_is_rejected_should_raise_without_the_key(self):
        api = AlchemyApi("wrong-key", self.url_template)

        with raises(AlchemyException, match="HTTP 401") as error:
            api.get_asset_transfers(Network.BASE, "0xwallet", "from")

        assert "wrong-key" not in str(error.value)

    def when_call_fails_should_raise_without_the_key(self):
        with raises(AlchemyException, match="alchemy_getAssetTransfers") as error:
            self.api.get_asset_transfers(Network.BASE, "erroring", "from")

        assert API_KEY not in str(error.value)

    def when_unreachable_should_raise_without_the_url(self):
        api = AlchemyApi(API_KEY, "http://127.0.0.1:9/{subdomain}/{api_key}")

        with raises(AlchemyException) as error:
            api.get_asset_transfers(Network.BASE, "0xwallet", "from")

        assert API_KEY not in str(error.value)
        assert error.value.__cause__ is None
