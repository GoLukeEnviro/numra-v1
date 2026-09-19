"""Register-endpoint rate limit (5/hour per client IP, `routes/auth.py`).

The companion test for `/v1/auth/login` lives in `test_auth_flow.py`. The register
limit is the one that blocks repeat acceptance runs: the RC2 journey registers two
accounts per viewport through the Next.js proxy, so the API sees one shared client
IP and a second run inside the hour fails with `RATE_LIMIT_EXCEEDED`. It had no
integration test of its own.

Each test builds its own app instance (`allow_self_signup=True`), so the in-memory
limiter starts empty: no dependency on leftover Redis state and no clock
manipulation. Key-namespace separation is asserted too -- register and login count
against distinct `auth:*` scopes, so exhausting one must not lock the other out.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from numra_api.app import create_app
from numra_api.config import Settings
from numra_api.db import build_sessionmaker

pytestmark = pytest.mark.integration

#: 5/hour per IP in `routes/auth.py::register`; the 6th request is the first denial.
REGISTER_LIMIT = 5


@pytest_asyncio.fixture
async def signup_client(settings: Settings, db_engine) -> AsyncIterator[AsyncClient]:
    """A client whose app has self-signup enabled (the deployment policy the RC2
    stack and CI run with) against the same test database."""
    app = create_app(settings=settings.model_copy(update={"allow_self_signup": True}))
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


async def test_register_limit_allows_five_then_rejects_the_sixth(signup_client) -> None:
    for index in range(REGISTER_LIMIT):
        response = await signup_client.post(
            "/v1/auth/register",
            json={"email": f"reg-limit-{index}@example.com", "password": "password12345"},
        )
        assert response.status_code == 201, f"attempt {index + 1} must be allowed: {response.text}"

    blocked = await signup_client.post(
        "/v1/auth/register",
        json={"email": "reg-limit-blocked@example.com", "password": "password12345"},
    )
    assert blocked.status_code == 429
    body = blocked.json()
    assert body["code"] == "RATE_LIMIT_EXCEEDED"
    # The client is told when to retry, within the still-open window -- not a
    # fabricated or zero value.
    retry_after = int(blocked.headers["retry-after"])
    assert 0 < retry_after <= 3600

    # The sixth attempt must NOT have created an account: the limiter runs as a
    # dependency before the route body, so it blocks before any write.
    login = await signup_client.post(
        "/v1/auth/login",
        json={"email": "reg-limit-blocked@example.com", "password": "password12345"},
    )
    assert login.status_code == 401, "a rate-limited registration must not have created a user"


async def test_register_limit_does_not_consume_the_login_limit(signup_client) -> None:
    """Separate key namespaces: exhausting `auth:register` must leave `auth:login`
    usable. A single shared counter would couple two unrelated limits."""
    for index in range(REGISTER_LIMIT + 1):
        await signup_client.post(
            "/v1/auth/register",
            json={"email": f"reg-sep-{index}@example.com", "password": "password12345"},
        )

    # The register window is exhausted...
    exhausted = await signup_client.post(
        "/v1/auth/register",
        json={"email": "reg-sep-late@example.com", "password": "password12345"},
    )
    assert exhausted.status_code == 429

    # ...but login is a different counter and still answers normally.
    login = await signup_client.post(
        "/v1/auth/login",
        json={"email": "nobody@example.com", "password": "wrong-password"},
    )
    assert login.status_code == 401
    assert login.json()["code"] != "RATE_LIMIT_EXCEEDED"
