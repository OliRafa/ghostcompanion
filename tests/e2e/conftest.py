"""Shared fixtures for end-to-end tests that hit a real Ghostfolio instance.

We hit a live/prod Ghostfolio, so the suite is deliberately gentle on it and
leaves nothing behind:

- By default it creates ONE throwaway anonymous user for the whole session and
  deletes it at the end via Ghostfolio's ``deleteOwnUser`` endpoint (``DELETE
  /user`` with the security token in the body). Deleting the user cascades to
  its accounts and activities, so the net footprint on prod is zero.
- If ``GHOSTFOLIO_ACCOUNT_TOKEN`` is set (e.g. a dedicated CI user), that user is
  reused instead of created. It is never deleted; its accounts/activities are
  wiped before and after the session so nothing dangles.

Target instance comes from ``GHOSTFOLIO_BASE_URL`` (defaults to the public
``https://ghostfol.io``, matching the app's ``Settings``).
"""

import logging
from os import getenv
from pathlib import Path

import pytest
import requests
from requests import Session

from ghostcompanion.configs.settings import GhostfolioSettings
from ghostcompanion.infra.ghostfolio.ghostfolio_adapter import GhostfolioAdapter
from ghostcompanion.infra.ghostfolio.ghostfolio_api import GhostfolioApi

_TIMEOUT = 30
_API_LOG = logging.getLogger("e2e.ghostfolio_api")


def _api_base_url() -> str:
    root = getenv("GHOSTFOLIO_BASE_URL", "https://ghostfol.io")
    return f"{root}/api/v1"


def _create_anonymous_user(base_url: str) -> str:
    response = requests.post(f"{base_url}/user", timeout=_TIMEOUT)
    response.raise_for_status()
    return response.json()["accessToken"]


def _auth_header(base_url: str, account_token: str) -> dict[str, str]:
    response = requests.post(
        f"{base_url}/auth/anonymous",
        data={"accessToken": account_token},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['authToken']}"}


def _account_ids(base_url: str, header: dict[str, str]) -> set[str]:
    response = requests.get(f"{base_url}/account", headers=header, timeout=_TIMEOUT)
    response.raise_for_status()
    return {account["id"] for account in response.json()["accounts"]}


def _activity_ids(base_url: str, header: dict[str, str]) -> list[str]:
    response = requests.get(f"{base_url}/activities", headers=header, timeout=_TIMEOUT)
    response.raise_for_status()
    return [activity["id"] for activity in response.json()["activities"]]


def _wipe_user(base_url: str, header: dict[str, str]) -> None:
    """Remove all of the user's data. Ghostfolio refuses to delete an account
    that still has activities, so activities go first, then the accounts."""
    for activity_id in _activity_ids(base_url, header):
        requests.delete(
            f"{base_url}/activities/{activity_id}", headers=header, timeout=_TIMEOUT
        )
    for account_id in _account_ids(base_url, header):
        requests.delete(
            f"{base_url}/account/{account_id}", headers=header, timeout=_TIMEOUT
        )


def _delete_own_user(base_url: str, header: dict[str, str], account_token: str) -> None:
    """Delete the current user (cascades its accounts and activities).

    Ghostfolio's self-delete route is ``DELETE /user`` carrying the security
    token in the body — distinct from the admin-only ``DELETE /user/:id``."""
    response = requests.delete(
        f"{base_url}/user",
        headers=header,
        json={"accessToken": account_token},
        timeout=_TIMEOUT,
    )
    response.raise_for_status()


def _log_file_path() -> Path:
    override = getenv("GHOSTFOLIO_E2E_API_LOG")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "e2e-api.log"


def _summarize_body(body) -> str:
    if isinstance(body, dict):
        body = {
            key: ("***" if key == "accessToken" else value)
            for key, value in body.items()
        }
    text = repr(body)
    return text if len(text) <= 2000 else f"{text[:2000]}…"


@pytest.fixture(scope="session")
def log_ghostfolio_api():
    """Record every Ghostfolio API request (method, URL, status, and write body)
    to a file, so what the suite did against the instance can be reviewed. Wraps
    ``Session.request``, which every ``requests`` call funnels through — so both
    these fixtures and the app's own ``GhostfolioApi`` are captured."""
    handler = logging.FileHandler(_log_file_path(), mode="w")
    handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s"))
    _API_LOG.addHandler(handler)
    _API_LOG.setLevel(logging.INFO)
    _API_LOG.propagate = False

    original_request = Session.request

    def logging_request(self, method, url, *args, **kwargs):
        response = original_request(self, method, url, *args, **kwargs)
        verb = method.upper()
        body = kwargs.get("json")
        if body is None:
            body = kwargs.get("data")
        detail = f"  {_summarize_body(body)}" if verb != "GET" and body else ""
        _API_LOG.info("%s %s -> %s%s", verb, url, response.status_code, detail)
        return response

    Session.request = logging_request
    yield
    Session.request = original_request
    _API_LOG.removeHandler(handler)
    handler.close()


@pytest.fixture(scope="session")
def ghostfolio_base_url() -> str:
    base_url = _api_base_url()
    try:
        health = requests.get(f"{base_url}/health", timeout=_TIMEOUT)
        health.raise_for_status()
    except requests.RequestException as error:
        raise RuntimeError(
            f"Ghostfolio is not reachable at {base_url}. Start it (or set "
            f"GHOSTFOLIO_BASE_URL) before running the e2e suite. Original error: "
            f"{error}"
        ) from error
    return base_url


@pytest.fixture(scope="session")
def ghostfolio_session(ghostfolio_base_url, log_ghostfolio_api):
    """Provide a clean Ghostfolio user for the session and clean up after.

    Reuses ``GHOSTFOLIO_ACCOUNT_TOKEN`` if set (kept, only wiped); otherwise
    creates a throwaway user and deletes it entirely at the end.
    """
    provided_token = getenv("GHOSTFOLIO_ACCOUNT_TOKEN", "") or (
        GhostfolioSettings.ACCOUNT_TOKEN
    )
    owns_user = not provided_token
    _API_LOG.info(
        "session start: base=%s mode=%s",
        ghostfolio_base_url,
        "ephemeral (create + delete own user)" if owns_user else "reuse provided user",
    )
    account_token = (
        _create_anonymous_user(ghostfolio_base_url) if owns_user else provided_token
    )
    header = _auth_header(ghostfolio_base_url, account_token)

    _wipe_user(ghostfolio_base_url, header)
    yield ghostfolio_base_url, account_token, header

    if owns_user:
        _delete_own_user(ghostfolio_base_url, header, account_token)
    else:
        _wipe_user(ghostfolio_base_url, header)
    _API_LOG.info("session end: cleanup complete")


@pytest.fixture
def ghostfolio(monkeypatch, ghostfolio_session) -> GhostfolioAdapter:
    base_url, account_token, _ = ghostfolio_session
    monkeypatch.setattr(GhostfolioSettings, "BASE_URL", base_url)
    monkeypatch.setattr(GhostfolioSettings, "ACCOUNT_TOKEN", account_token)
    return GhostfolioAdapter(GhostfolioApi())
