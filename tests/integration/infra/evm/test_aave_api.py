import json
import threading
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pytest import fixture

from ghostcompanion.core.entity.lending import LendingReserve
from ghostcompanion.core.entity.wallet import Network
from ghostcompanion.infra.evm.aave_api import AaveApi
from ghostcompanion.infra.evm.alchemy_api import AlchemyApi

BASE_POOL = "0xa238dd80c259a72e81d7e4664a9801593f98d1c5"
USDC = "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913"
UNLISTED = "0x3764f07752384450576c6d8b027d06ffa29e5ae9"
A_USDC = "0x4e65fe4dba92790696d040ac24aa414708f5c0ab"
DEBT_USDC = "0x59dca05b6c26dbd64b5381374aaac5cd05644c28"
OWNER = "0x2222222222222222222222222222222222222222"


def word(value: int | str) -> str:
    if isinstance(value, str):
        return value.removeprefix("0x").rjust(64, "0")
    return f"{value:064x}"


def reserve_data(supply_token: str, debt_token: str) -> str:
    words = [word(0)] * 15
    words[8] = word(supply_token)
    words[10] = word(debt_token)
    return "0x" + "".join(words)


def call_data(selector: str, address: str) -> str:
    return selector + word(address)


ANSWERS = {
    (BASE_POOL, call_data("0x35ea6a75", USDC)): reserve_data(A_USDC, DEBT_USDC),
    (BASE_POOL, call_data("0x35ea6a75", UNLISTED)): "0x" + word(0) * 15,
    (A_USDC, "0x313ce567"): "0x" + word(6),
    (A_USDC, call_data("0x70a08231", OWNER)): "0x" + word(1_250_500_000),
    (DEBT_USDC, call_data("0x70a08231", OWNER)): "0x" + word(2_104_377_605),
}


class FakeNode(BaseHTTPRequestHandler):
    """Answers `eth_call` batches from a table of (contract, call data)."""

    calls: list[dict] = []

    def do_POST(self):
        calls = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeNode.calls += calls
        answers = [
            {
                "jsonrpc": "2.0",
                "id": call["id"],
                "result": ANSWERS[(call["params"][0]["to"], call["params"][0]["data"])],
            }
            for call in calls
        ]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(answers).encode())

    def log_message(self, *args):
        ...


class AaveApiFactory:
    @fixture(autouse=True)
    def initialize_api(self):
        FakeNode.calls = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), FakeNode)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        alchemy_api = AlchemyApi(
            "key", f"http://127.0.0.1:{server.server_port}/{{subdomain}}/{{api_key}}"
        )
        self.api = AaveApi(alchemy_api)
        yield
        server.shutdown()
        server.server_close()


USDC_RESERVE = LendingReserve(
    network=Network.BASE,
    asset=USDC,
    supply_token=A_USDC,
    debt_token=DEBT_USDC,
    decimals=6,
)


class TestGetReserves(AaveApiFactory):
    def should_find_the_tokens_the_core_market_keeps_for_a_coin(self):
        assert self.api.get_reserves(Network.BASE, [USDC]) == [USDC_RESERVE]

    def when_market_does_not_lend_a_coin_should_leave_it_out(self):
        assert self.api.get_reserves(Network.BASE, [UNLISTED, USDC]) == [USDC_RESERVE]

    def when_network_has_no_market_should_ask_nothing(self):
        assert self.api.get_reserves(Network.BITCOIN, [USDC]) == []
        assert FakeNode.calls == []


class TestGetPositions(AaveApiFactory):
    def should_read_what_was_supplied_and_borrowed_in_coins(self):
        [position] = self.api.get_positions(Network.BASE, OWNER, [USDC_RESERVE])

        assert position.reserve == USDC_RESERVE
        assert position.supplied == Decimal("1250.5")
        assert position.borrowed == Decimal("2104.377605")

    def should_read_every_balance_in_one_batch(self):
        self.api.get_positions(Network.BASE, OWNER, [USDC_RESERVE])

        assert [call["params"][0]["to"] for call in FakeNode.calls] == [
            A_USDC,
            DEBT_USDC,
        ]

    def when_there_are_no_reserves_should_ask_nothing(self):
        assert self.api.get_positions(Network.BASE, OWNER, []) == []
        assert FakeNode.calls == []


CBBTC = "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf"
A_CBBTC = "0xbdb9300b7cde636d9cd4aff00f6f009ffbbc8ee6"
DEBT_CBBTC = "0x05e08702028de6aad395dc6478b554a56920b9ad"
CBBTC_RESERVE = LendingReserve(
    network=Network.BASE,
    asset=CBBTC,
    supply_token=A_CBBTC,
    debt_token=DEBT_CBBTC,
    decimals=8,
)
NO_ADDRESS = "0x" + "0" * 40
SETTLEMENT = "0x9008d19f58aabd9ed0d60971565aa8510560ab41"
OTHER = "0x3333333333333333333333333333333333333333"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
MINT = "0x458f5fa412d0f69b08dd84872b0215675cc67bc1d5b6fd93300a1c3878b86196"
BURN = "0x4cf25bc1d991c17529c25213d3cc0cda295eeaad5f13f361969b12ea48015f90"
INDEX = 10**27


def log(token: str, topic: str, first: str, second: str, *values: int) -> dict:
    return {
        "address": token,
        "topics": ["0x" + word(topic), "0x" + word(first), "0x" + word(second)],
        "data": "0x" + "".join(word(value) for value in values),
    }


def receipt(*logs: dict) -> dict:
    return {"transactionHash": "0x" + "ab" * 32, "logs": list(logs)}


class TestGetChanges(AaveApiFactory):
    def changes(self, *logs: dict) -> list:
        return self.api.get_changes(
            OWNER, [USDC_RESERVE, CBBTC_RESERVE], receipt(*logs)
        )

    def when_supplying_should_split_the_principal_from_the_interest(self):
        [change] = self.changes(
            log(A_USDC, TRANSFER, NO_ADDRESS, OWNER, 3_910_006),
            log(A_USDC, MINT, OWNER, OWNER, 3_910_006, 6, INDEX),
        )

        assert change.reserve == USDC_RESERVE
        assert (change.supplied, change.interest_earned) == (
            Decimal("3.91"),
            Decimal("0.000006"),
        )

    def when_withdrawing_should_add_the_interest_to_what_was_burnt(self):
        [change] = self.changes(
            log(A_USDC, TRANSFER, OWNER, NO_ADDRESS, 9_412_305),
            log(A_USDC, BURN, OWNER, OWNER, 9_412_305, 73_518, INDEX),
        )

        assert (change.supplied, change.interest_earned) == (
            Decimal("-9.485823"),
            Decimal("0.073518"),
        )

    def when_borrowing_should_owe_the_principal_and_the_interest(self):
        [change] = self.changes(
            log(DEBT_USDC, MINT, OWNER, OWNER, 218_214_878, 5_214_877, INDEX)
        )

        assert (change.borrowed, change.interest_due) == (
            Decimal("213.000001"),
            Decimal("5.214877"),
        )

    def when_someone_repays_for_the_owner_should_still_be_a_repayment(self):
        [change] = self.changes(
            log(DEBT_USDC, BURN, OWNER, NO_ADDRESS, 868_221_177, 7_418_235, INDEX)
        )

        assert (change.borrowed, change.interest_due) == (
            Decimal("-875.639412"),
            Decimal("7.418235"),
        )

    def when_repaying_less_than_the_interest_should_be_a_repayment(self):
        # The debt still grew, by the 15 interest due less the 10 paid.
        [change] = self.changes(log(DEBT_USDC, MINT, OWNER, OWNER, 5, 15, INDEX))

        assert (change.borrowed, change.interest_due) == (
            Decimal("-0.00001"),
            Decimal("0.000015"),
        )

    def when_swapping_collateral_should_count_supply_tokens_sent_and_received(self):
        changes = self.changes(
            log(A_USDC, TRANSFER, NO_ADDRESS, OWNER, 613_407),
            log(A_USDC, MINT, SETTLEMENT, OWNER, 613_407, 613_407, INDEX),
            log(A_USDC, TRANSFER, OWNER, SETTLEMENT, 850_423_150),
            log(A_CBBTC, TRANSFER, SETTLEMENT, OWNER, 1_042_117),
        )

        by_reserve = {x.reserve.asset: x for x in changes}
        usdc, cbbtc = by_reserve[USDC], by_reserve[CBBTC]
        assert (usdc.supplied, usdc.transferred, usdc.interest_earned) == (
            Decimal("0"),
            Decimal("-850.42315"),
            Decimal("0.613407"),
        )
        assert (cbbtc.supplied, cbbtc.transferred) == (0, Decimal("0.01042117"))

    def should_only_read_the_owners_events(self):
        assert (
            self.changes(
                log(A_USDC, MINT, OTHER, OTHER, 100, 1, INDEX),
                log(A_USDC, TRANSFER, OTHER, SETTLEMENT, 100),
                log(DEBT_USDC, BURN, OTHER, NO_ADDRESS, 100, 1, INDEX),
            )
            == []
        )

    def should_only_read_the_reserves_tokens(self):
        assert self.changes(log(USDC, TRANSFER, OWNER, SETTLEMENT, 100)) == []

    def when_receipt_has_no_logs_should_have_no_changes(self):
        assert self.api.get_changes(OWNER, [USDC_RESERVE], {"logs": []}) == []
        assert FakeNode.calls == []
