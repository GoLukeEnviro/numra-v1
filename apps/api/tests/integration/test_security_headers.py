"""PWA-08: the API's security-header contract.

`SecurityHeadersMiddleware` was previously untested, which is how a real gap -- no
`Strict-Transport-Security` on any API response -- shipped unnoticed. The web
middleware's matcher excludes `/api/*`, so these headers (and only these) cover the
API surface; a dropped or weakened header must fail here.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from numra_api.app import create_app
from numra_api.config import Settings

pytestmark = pytest.mark.integration

_DB_URL = "postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_test"


@pytest.fixture
def header_client() -> AsyncClient:
    """A client against a minimal app; these assertions need no database."""
    settings = Settings(
        database_url=_DB_URL,
        environment="test",
        numra_llm_provider="mock",
        export_storage_dir="/tmp/security-headers-test",
    )
    app = create_app(settings=settings)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def test_api_responses_carry_the_full_security_header_set(header_client) -> None:
    """Every documented header, by name and value -- not just "some CSP is present"."""
    async with header_client as client:
        response = await client.get("/v1/public/config")

    assert response.status_code == 200
    headers = {key.lower(): value for key, value in response.headers.items()}

    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert headers["permissions-policy"] == "geolocation=(), microphone=(), camera=()"
    # The API is JSON-only: nothing may be loaded or framed from it.
    assert headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"


async def test_api_responses_send_hsts(header_client) -> None:
    """Without this the API answers carry no transport policy at all.

    The web middleware excludes `/api/*`, so HSTS on the API surface can only come
    from `SecurityHeadersMiddleware` -- the exact line whose absence was the finding.
    """
    async with header_client as client:
        response = await client.get("/v1/public/config")

    hsts = response.headers.get("strict-transport-security")
    assert hsts is not None, "the API must send Strict-Transport-Security"
    assert "max-age=" in hsts
    max_age = int(hsts.split("max-age=")[1].split(";")[0])
    assert max_age >= 31_536_000, "at least one year, per common guidance"
    # Both are deliberate omissions (tunnel sub-zone is not ours; preload is one-way).
    assert "includeSubDomains" not in hsts
    assert "preload" not in hsts


async def test_security_headers_also_apply_to_error_responses(header_client) -> None:
    """An error response must not be a headerless escape hatch.

    The exact status is deliberately not asserted: this client has no database
    fixtures, so an auth-required route may answer 404 (unknown route state) or 401
    depending on how far it gets before the dependency fails. What matters -- and
    what the middleware must guarantee for EVERY `http.response.start` -- is that
    the headers are present regardless of status.
    """
    async with header_client as client:
        response = await client.get("/v1/definitely-not-a-route")

    assert response.status_code >= 400
    headers = {key.lower(): value for key, value in response.headers.items()}
    assert headers.get("strict-transport-security") is not None
    assert headers.get("x-content-type-options") == "nosniff"
