import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, final, override
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
                "comment": "Created by Ghostcompanion.",
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
        self._balances: dict[str, list[dict]] = {}  # account_id -> balances
        self._api_call_count = 0  # Track API calls for optimization tests

    @override
    def get_orders(self, account_id: str | None = None) -> dict[str, Any]:
        return list(filter(lambda x: x["Account"]["id"] == account_id, self._orders))

    def _load_orders(self) -> list[dict[str, Any]]:
        orders_file = (
            Path(__file__).parents[1].joinpath("resources", "ghostfolio", "orders.json")
        )
        with orders_file.open("r") as buffer:
            return json.load(buffer)

    @override
    def get_accounts(self) -> list[dict[str, Any]]:
        return self._accounts

    @override
    def create_account(self, account_data: dict[str, Any]) -> dict[str, Any]:
        account_data["id"] = str(uuid4())
        self._accounts.append(account_data)
        return account_data

    @override
    def delete_order_by_id(self, order_id: str):
        order = next(filter(lambda x: x["id"] == order_id, self._orders))
        self._orders.remove(order)

    @override
    def insert_orders(self, orders: list[dict[str, str | float]]):
        for order in orders:
            order["id"] = str(uuid4())
            order["comment"] = order["comment"] or ""
            order["Account"] = {"id": order["accountId"]}
            del order["accountId"]

            order["SymbolProfile"] = {"symbol": order["symbol"]}
            del order["symbol"]

        self._orders += orders

    # Cash Balance Methods

    @override
    def get_account_balances(self, account_id: str) -> list[dict]:
        self._api_call_count += 1
        return self._balances.get(account_id, [])

    @override
    def create_account_balance(
        self, account_id: str, date: date, value: Decimal
    ) -> dict:
        self._api_call_count += 1
        balance = {
            "id": str(uuid4()),
            "date": date.isoformat(),
            "value": float(value),
        }
        if account_id not in self._balances:
            self._balances[account_id] = []
        self._balances[account_id].append(balance)
        return balance

    # Test helper methods

    def get_api_call_count(self) -> int:
        """Get the number of API calls made (for testing optimization)."""
        return self._api_call_count

    def reset_api_call_count(self) -> None:
        """Reset the API call counter."""
        self._api_call_count = 0

    def get_balances_for_account(self, account_id: str) -> list[dict]:
        """Test helper to get balances for an account."""
        return self._balances.get(account_id, [])

    def clear_balances(self) -> None:
        """Clear all balances (for test isolation)."""
        self._balances.clear()
        self._api_call_count = 0
