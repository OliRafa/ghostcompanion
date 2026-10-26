from collections import defaultdict
from decimal import Decimal
from typing import Any, final

from ghostcompanion.core.entity.lending import (
    LendingChange,
    LendingPosition,
    LendingReserve,
)
from ghostcompanion.core.entity.wallet import Network
from ghostcompanion.core.ports.lending_market import LendingMarketPort
from ghostcompanion.infra.evm.alchemy_api import AlchemyApi

# Aave v3's main ("core") market on each network.
_POOLS = {
    Network.ETHEREUM: "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2",
    Network.BASE: "0xa238dd80c259a72e81d7e4664a9801593f98d1c5",
}
_GET_RESERVE_DATA = "0x35ea6a75"
_BALANCE_OF = "0x70a08231"
_DECIMALS = "0x313ce567"
# Where Pool.getReserveData puts each token among the words it answers with.
_SUPPLY_TOKEN_WORD = 8
_VARIABLE_DEBT_TOKEN_WORD = 10
_NO_ADDRESS = "0x" + "0" * 40
_TRANSFER = "ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
# The market's tokens announce every change to a balance along with the interest
# accrued on it since the last one, as (value, balanceIncrease, index): Mint when
# the balance grew, to `onBehalfOf`, and Burn when it shrank, from `from`.
_MINT = "458f5fa412d0f69b08dd84872b0215675cc67bc1d5b6fd93300a1c3878b86196"
_BURN = "4cf25bc1d991c17529c25213d3cc0cda295eeaad5f13f361969b12ea48015f90"


@final
class AaveApi(LendingMarketPort):
    def __init__(self, alchemy_api: AlchemyApi):
        self._alchemy_api = alchemy_api

    def get_reserves(self, network: Network, assets: list[str]) -> list[LendingReserve]:
        pool = _POOLS.get(network)
        if pool is None or not assets:
            return []

        answers = self._alchemy_api.call_contracts(
            network, [(pool, _GET_RESERVE_DATA + _encode(asset)) for asset in assets]
        )
        listed = []
        for asset, answer in zip(assets, answers):
            words = _decode(answer)
            # A coin the market doesn't lend comes back as all zeros.
            if len(words) <= _VARIABLE_DEBT_TOKEN_WORD:
                continue
            supply_token = _address(words[_SUPPLY_TOKEN_WORD])
            if supply_token == _NO_ADDRESS:
                continue
            listed.append(
                (asset, supply_token, _address(words[_VARIABLE_DEBT_TOKEN_WORD]))
            )

        decimals = self._alchemy_api.call_contracts(
            network, [(supply_token, _DECIMALS) for _, supply_token, _ in listed]
        )
        return [
            LendingReserve(
                network=network,
                asset=asset,
                supply_token=supply_token,
                debt_token=debt_token,
                decimals=int(places, 16),
            )
            for (asset, supply_token, debt_token), places in zip(listed, decimals)
        ]

    def get_positions(
        self, network: Network, owner: str, reserves: list[LendingReserve]
    ) -> list[LendingPosition]:
        if not reserves:
            return []

        answers = iter(
            self._alchemy_api.call_contracts(
                network,
                [
                    (token, _BALANCE_OF + _encode(owner))
                    for reserve in reserves
                    for token in (reserve.supply_token, reserve.debt_token)
                ],
            )
        )
        positions = []
        for reserve in reserves:
            unit = Decimal(10) ** reserve.decimals
            supplied = Decimal(int(next(answers), 16)) / unit
            borrowed = Decimal(int(next(answers), 16)) / unit
            positions.append(
                LendingPosition(reserve=reserve, supplied=supplied, borrowed=borrowed)
            )
        return positions

    def get_changes(
        self, owner: str, reserves: list[LendingReserve], receipt: dict[str, Any]
    ) -> list[LendingChange]:
        sides = {}
        for reserve in reserves:
            sides[reserve.supply_token] = (reserve, "supplied", "interest_earned")
            sides[reserve.debt_token] = (reserve, "borrowed", "interest_due")

        owner_word = _encode(owner)
        no_address = _encode(_NO_ADDRESS)
        totals: dict[LendingReserve, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        for log in receipt.get("logs", []):
            side = sides.get(log["address"].lower())
            if side is None:
                continue
            reserve, principal, interest = side
            topic, *indexed = [x.lower().removeprefix("0x") for x in log["topics"]]
            words = [int(x, 16) for x in _decode(log["data"])]
            if topic == _MINT and indexed[1] == owner_word:
                value, increase = words[:2]
                totals[reserve][principal] += value - increase
                totals[reserve][interest] += increase
            elif topic == _BURN and indexed[0] == owner_word:
                value, increase = words[:2]
                totals[reserve][principal] -= value + increase
                totals[reserve][interest] += increase
            elif topic == _TRANSFER and principal == "supplied":
                # Mints and burns go to or come from no address, and are told by
                # their own events above.
                source, target = indexed
                if no_address in (source, target) or source == target:
                    continue
                if target == owner_word:
                    totals[reserve]["transferred"] += words[0]
                elif source == owner_word:
                    totals[reserve]["transferred"] -= words[0]

        return [
            LendingChange(
                reserve=reserve,
                **{
                    field: Decimal(amount) / Decimal(10) ** reserve.decimals
                    for field, amount in amounts.items()
                },
            )
            for reserve, amounts in totals.items()
            if any(amounts.values())
        ]


def _encode(address: str) -> str:
    return address.lower().removeprefix("0x").rjust(64, "0")


def _decode(answer: str) -> list[str]:
    data = answer.removeprefix("0x")
    return [data[start : start + 64] for start in range(0, len(data), 64)]


def _address(word: str) -> str:
    return "0x" + word[-40:]
