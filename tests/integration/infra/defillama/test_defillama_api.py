import json
import threading
from datetime import datetime, timezone
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from pytest import fixture, raises

from ghostcompanion.infra.defillama.defillama_api import (
    DefiLlamaApi,
    DefiLlamaException,
)

CBBTC = "base:0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf"
MOMENT = datetime(2026, 9, 17, 8, 41, 12, tzinfo=timezone.utc)
TIMESTAMP = int(MOMENT.timestamp())


class FakeDefiLlama(BaseHTTPRequestHandler):
    """Answers like DefiLlama's historical prices: a point 11 s after the moment
    for cbBTC, one two hours off for `far`, nothing for `unknown`, one rate limit
    for `limited` and a server error for `broken`."""

    requests: list[tuple[str, dict[str, list[str]]]] = []
    rate_limited_once = False

    def do_GET(self):
        url = urlparse(self.path)
        FakeDefiLlama.requests.append((url.path, parse_qs(url.query)))
        _, _, _, timestamp, coin = url.path.split("/")
        if coin == "limited" and not FakeDefiLlama.rate_limited_once:
            FakeDefiLlama.rate_limited_once = True
            return self._reply(429, {"message": "slow down"})
        if coin == "broken":
            return self._reply(500, {"message": "internal error"})

        offsets = {CBBTC: 11, "limited": 0, "far": 2 * 3600}
        if coin not in offsets:
            return self._reply(200, {"coins": {}})
        point = {"price": 76318.55, "timestamp": int(timestamp) + offsets[coin]}
        self._reply(200, {"coins": {coin: point}})

    def _reply(self, status: int, body):
        self.send_response(status)
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def log_message(self, *args):
        ...


class DefiLlamaApiFactory:
    @fixture(autouse=True)
    def initialize_api(self):
        FakeDefiLlama.requests = []
        FakeDefiLlama.rate_limited_once = False
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeDefiLlama)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.api = DefiLlamaApi(f"http://127.0.0.1:{server.server_port}")
        yield
        server.shutdown()
        server.server_close()


class TestGetPrice(DefiLlamaApiFactory):
    def should_return_the_price_closest_to_the_moment(self):
        assert self.api.get_price(CBBTC, MOMENT) == Decimal("76318.55")

    def should_ask_for_the_moment_within_an_hour(self):
        self.api.get_price(CBBTC, MOMENT)

        [(path, query)] = FakeDefiLlama.requests
        assert path == f"/prices/historical/{TIMESTAMP}/{CBBTC}"
        assert query == {"searchWidth": ["60m"]}

    def when_coin_is_unknown_should_return_none(self):
        assert self.api.get_price("unknown", MOMENT) is None

    def when_closest_point_is_over_an_hour_away_should_return_none(self):
        assert self.api.get_price("far", MOMENT) is None

    def when_rate_limited_should_retry(self, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda _: None)

        assert self.api.get_price("limited", MOMENT) == Decimal("76318.55")


class TestErrors(DefiLlamaApiFactory):
    def when_server_keeps_failing_should_raise(self, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda _: None)

        with raises(DefiLlamaException, match="HTTP 500"):
            self.api.get_price("broken", MOMENT)

        assert len(FakeDefiLlama.requests) == 4

    def when_unreachable_should_raise_without_the_cause(self):
        api = DefiLlamaApi("http://127.0.0.1:9")

        with raises(DefiLlamaException) as error:
            api.get_price(CBBTC, MOMENT)

        assert error.value.__cause__ is None
