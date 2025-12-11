import json
from pathlib import Path
from typing import Any, final
from uuid import uuid4

from ghostcompanion.core.ports.ghostfolio import GhostfolioPort


@final
class InMemoryGhostfolioApi(GhostfolioPort):
    def __init__(self):
        self._accounts = [
            {
                "balance": 0,
                "comment": None,
                "createdAt": "2025-01-16T18:56:16.071Z",
                "currency": "USD",
                "id": "39495da9-9d47-469b-adf1-321f66004332",
                "isExcluded": False,
                "name": "A Account",
                "platformId": None,
                "updatedAt": "2025-01-16T18:56:16.071Z",
                "userId": "933030a7-c6eb-42d0-bf05-52e978f3ca5e",
                "Platform": None,
                "transactionCount": 0,
                "valueInBaseCurrency": 0,
                "balanceInBaseCurrency": 0,
                "value": 0,
            },
            {
                "balance": 0,
                "comment": "Created by Tastytrade-Ghostfolio.",
                "createdAt": "2025-01-16T18:56:45.495Z",
                "currency": "USD",
                "id": "2a7efb1f-8f3c-43de-8778-f8488f1719d3",
                "isExcluded": False,
                "name": "Tastytrade",
                "platformId": None,
                "updatedAt": "2025-01-16T18:56:45.495Z",
                "userId": "933030a7-c6eb-42d0-bf05-52e978f3ca5e",
                "Platform": None,
                "transactionCount": 131,
                "valueInBaseCurrency": 5892.889062299996,
                "balanceInBaseCurrency": 0,
                "value": 5892.889062299996,
            },
        ]
        self._orders = self._load_orders()

    def get_orders(self, account_id: str | None = None) -> dict:
        return list(filter(lambda x: x["Account"]["id"] == account_id, self._orders))

    def _load_orders(self) -> list[dict]:
        orders_file = (
            Path(__file__).parents[1].joinpath("resources", "ghostfolio", "orders.json")
        )
        with orders_file.open("r") as buffer:
            return json.load(buffer)

    def get_accounts(self) -> list[dict[str, Any]]:
        return self._accounts

    def create_account(self, account_data: dict[str, Any]) -> dict[str, Any]:
        account_data["id"] = str(uuid4())
        self._accounts.append(account_data)
        return account_data

    def delete_order_by_id(self, order_id: str):
        order = next(filter(lambda x: x["id"] == order_id, self._orders))
        self._orders.remove(order)

    def insert_orders(self, orders: list[dict[str, str | float]]):
        for order in orders:
            order["id"] = str(uuid4())
            order["comment"] = ""
            order["Account"] = {"id": order["accountId"]}
            del order["accountId"]

            order["SymbolProfile"] = {"symbol": order["symbol"]}
            del order["symbol"]

        self._orders += orders
