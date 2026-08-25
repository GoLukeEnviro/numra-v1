from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from numra_api.app import create_app
from numra_api.config import Settings
from numra_api.db import build_sessionmaker

pytestmark = pytest.mark.integration

#: Substrings that must never appear in an unauthenticated response body, checked
#: case-insensitively -- config keys, connection strings and secret names alike.
FORBIDDEN_SUBSTRINGS = (
    "DATABASE_URL",
    "postgresql",
    "redis",
    "SESSION_SECRET",
    "OLLAMA",
    "pdf_internal_token",
    "environment",
)


def _client_with_self_signup(settings: Settings, db_engine, *, enabled: bool) -> AsyncClient:
    """Self-signup is a Settings flag resolved at app construction, so toggling it
    means a dedicated app instance -- same pattern the existing auth tests use."""
    app = create_app(
        settings=Settings(
            database_url=settings.database_url, environment="test", allow_self_signup=enabled
        )
    )
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def test_public_config_is_readable_without_any_cookie(client) -> None:
    """The sign-in page fetches this before any session can exist -- it must answer
    200 to a completely anonymous caller, unlike every other /v1 endpoint."""
    response = await client.get("/v1/public/config")

    assert response.status_code == 200
    assert response.json() == {
        "self_signup_enabled": False,
        "app_name": "NUMRA",
        "supported_ui_locales": ["de", "en"],
    }


@pytest.mark.parametrize("enabled", [True, False])
async def test_self_signup_enabled_mirrors_settings(
    settings: Settings, db_engine, enabled: bool
) -> None:
    async with _client_with_self_signup(settings, db_engine, enabled=enabled) as public_client:
        response = await public_client.get("/v1/public/config")

    assert response.status_code == 200
    assert response.json()["self_signup_enabled"] is enabled


async def test_public_config_leaks_no_infrastructure_details(client) -> None:
    """Guards the endpoint's whole reason for having its own narrow schema: nothing
    about the deployment (database, cache, LLM backend, secrets, environment name)
    may reach an anonymous caller."""
    response = await client.get("/v1/public/config")
    body = response.text.lower()

    for forbidden in FORBIDDEN_SUBSTRINGS:
        assert forbidden.lower() not in body
