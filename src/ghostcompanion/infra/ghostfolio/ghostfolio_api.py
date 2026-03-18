from datetime import date
from decimal import Decimal
from typing import Any, final

import requests

from ghostcompanion.configs.settings import GhostfolioSettings
from ghostcompanion.core.ports.ghostfolio import GhostfolioPort


@final
class GhostfolioApi(GhostfolioPort):
    def __init__(self):
        self.AUTHORIZATION_HEADER = self._get_ghostfolio_authorization_header()

    def _get_ghostfolio_authorization_header(self) -> dict[str, str]:
        """Log in the user and get its authenticated header.

        Returns
        -------
        dict[str, str]
            The authenticated header to be used in requests.

        Raises
        ------
        Exception
            When an HTTP error occurred while authenticating the user.
        """
        try:
            response = requests.post(
                f"{GhostfolioSettings.BASE_URL}/auth/anonymous",
                data={"accessToken": GhostfolioSettings.ACCOUNT_TOKEN},
            )
            response.raise_for_status()
            response_data = response.json()
            return {"Authorization": f"Bearer {response_data['authToken']}"}

        except requests.exceptions.HTTPError as ex:
            raise Exception(f"Error while authenticating with Ghostfolio: {ex}")

    def get_orders(self, account_id: str | None = None) -> dict:
        """Get all orders for the logged in user.

        Optionally, the returned orders are filtered for a given `account_id`.

        Parameters
        ----------
        account_id : str | None, optional
            ID of a particular account to filter the orders by, by default None.

        Returns
        -------
        list[GhostfolioActivity]
            User's orders.

        Raises
        ------
        Exception
            When an HTTP error occurred while requesting the orders.
        """
        try:
            if account_id:
                query_parameters = {"accounts": account_id}

            else:
                query_parameters = None

            response = requests.get(
                f"{GhostfolioSettings.BASE_URL}/order",
                headers=self.AUTHORIZATION_HEADER,
                params=query_parameters,
            )
            response.raise_for_status()
            return response.json()["activities"]

        except requests.exceptions.HTTPError as ex:
            raise Exception(f"Error while requesting orders to Ghostfolio: {ex}")

    def insert_orders(self, orders: list[dict[str, str | float]]):
        """Insert all activities into Ghostfolio for a particular user and account.

        Parameters
        ----------
        activities : list[GhostfolioActivity]
            Activities to be inserted in a particular account.

        Raises
        ------
        Exception
            When an HTTP error occurred while inserting the activities.
        """
        response = requests.post(
            f"{GhostfolioSettings.BASE_URL}/import",
            headers=self.AUTHORIZATION_HEADER,
            json={"activities": orders},
        )

        try:
            response.raise_for_status()

        except requests.exceptions.HTTPError:
            raise Exception(
                f"Error while inserting new activities in Ghostfolio: {response.json()}"
            )

    def get_accounts(self) -> list[dict[str, Any]]:
        """Get all accounts for the logged in user.

        Returns
        -------
        list[GhostfolioAccount]
            All accounts for the user.

        Raises
        ------
        Exception
            When an HTTP error occurred while fetching the accounts.
        """
        try:
            response = requests.get(
                f"{GhostfolioSettings.BASE_URL}/account",
                headers=self.AUTHORIZATION_HEADER,
            )
            response.raise_for_status()
            return response.json()["accounts"]

        except requests.exceptions.HTTPError as ex:
            raise Exception(f"Error while requesting accounts to Ghostfolio: {ex}")

    def create_account(self, account_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new account in Ghostfolio.

        Parameters
        ----------
        account : GhostfolioAccount
            Account parameters for creating a new account.

        Returns
        -------
        GhostfolioAccount
            The same account, now with the ID provided by Ghostfolio when creating.

        Raises
        ------
        Exception
            When the creation failed due to an HTTP error.
        """
        try:
            response = requests.post(
                f"{GhostfolioSettings.BASE_URL}/account",
                headers=self.AUTHORIZATION_HEADER,
                json=account_data,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as ex:
            raise Exception(f"Error while creating account in Ghostfolio: {ex}")

    def delete_order_by_id(self, order_id: str):
        response = requests.delete(
            f"{GhostfolioSettings.BASE_URL}/order/{order_id}",
            headers=self.AUTHORIZATION_HEADER,
        )

        try:
            response.raise_for_status()

        except requests.exceptions.HTTPError:
            raise Exception(
                f"Error while deleting order in Ghostfolio: {response.json()}"
            )

    # Cash Balance Methods

    def get_account_balances(self, account_id: str) -> list[dict]:
        """Get all cash balances for an account.

        Parameters
        ----------
        account_id : str
            The account ID to get balances for.

        Returns
        -------
        list[dict]
            List of balance objects with id, date, and value.
            Format: [{"id": "uuid", "date": "2024-01-15", "value": 1250.50}, ...]

        Raises
        ------
        Exception
            When the request fails.
        """
        try:
            response = requests.get(
                f"{GhostfolioSettings.BASE_URL}/account/{account_id}/balances",
                headers=self.AUTHORIZATION_HEADER,
            )
            response.raise_for_status()
            return response.json().get("balances", [])

        except requests.exceptions.HTTPError as ex:
            raise Exception(f"Error while fetching account balances: {ex}")

    def create_account_balance(
        self, account_id: str, date: date, value: Decimal
    ) -> dict:
        """Create a new cash balance for an account.

        Parameters
        ----------
        account_id : str
            The account ID.
        date : date
            The balance date.
        value : Decimal
            The cash balance value.

        Returns
        -------
        dict
            The created balance object.

        Raises
        ------
        Exception
            When the creation fails.
        """
        try:
            payload = {
                "accountId": account_id,
                "balance": float(value),
                "date": date.isoformat(),
            }

            response = requests.post(
                f"{GhostfolioSettings.BASE_URL}/account-balance",
                headers=self.AUTHORIZATION_HEADER,
                json=payload,
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as ex:
            raise Exception(f"Error while creating account balance: {ex}")
