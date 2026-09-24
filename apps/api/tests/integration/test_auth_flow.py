from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from numra_api.app import create_app
from numra_api.auth.passwords import hash_password
from numra_api.config import Settings
from numra_api.db import build_sessionmaker
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


async def _seed_user(sessionmaker, email: str, password: str) -> None:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password(password))
        await db.commit()


async def test_login_logout_me_flow(client, sessionmaker) -> None:
    await _seed_user(sessionmaker, "lukas@example.com", "correct horse battery staple")

    login_response = await client.post(
        "/v1/auth/login",
        json={"email": "lukas@example.com", "password": "correct horse battery staple"},
    )
    assert login_response.status_code == 200
    assert "numra_session" in login_response.cookies
    assert "numra_csrf" in login_response.cookies

    me_response = await client.get("/v1/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "lukas@example.com"

    logout_response = await client.post(
        "/v1/auth/logout", headers={"x-csrf-token": client.cookies["numra_csrf"]}
    )
    assert logout_response.status_code == 204

    me_after_logout = await client.get("/v1/auth/me")
    assert me_after_logout.status_code == 401
    assert me_after_logout.json()["code"] == "NOT_AUTHENTICATED"


async def test_session_cookie_name_is_configurable(settings: Settings, db_engine) -> None:
    """`session_cookie_name` must actually be read from Settings, not the hardcoded
    literal "numra_session" — regression test for the dead config finding: the name
    used to set/read/delete the cookie has to follow an env override end to end
    (login, /me, logout), not just exist on the Settings model."""
    custom_settings = settings.model_copy(update={"session_cookie_name": "numra_custom_session"})
    application = create_app(settings=custom_settings)
    application.state.engine = db_engine
    application.state.sessionmaker = build_sessionmaker(db_engine)

    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://testserver") as custom_client:
        await _seed_user(
            application.state.sessionmaker,
            "custom-cookie@example.com",
            "correct horse battery staple",
        )

        login_response = await custom_client.post(
            "/v1/auth/login",
            json={"email": "custom-cookie@example.com", "password": "correct horse battery staple"},
        )
        assert login_response.status_code == 200
        assert "numra_custom_session" in login_response.cookies
        assert "numra_session" not in login_response.cookies

        me_response = await custom_client.get("/v1/auth/me")
        assert me_response.status_code == 200
        assert me_response.json()["email"] == "custom-cookie@example.com"

        logout_response = await custom_client.post(
            "/v1/auth/logout", headers={"x-csrf-token": custom_client.cookies["numra_csrf"]}
        )
        assert logout_response.status_code == 204

        me_after_logout = await custom_client.get("/v1/auth/me")
        assert me_after_logout.status_code == 401
        assert me_after_logout.json()["code"] == "NOT_AUTHENTICATED"

        # Fourth call site: account deletion also has to clear the configured cookie
        # name, not the hardcoded literal.
        relogin_response = await custom_client.post(
            "/v1/auth/login",
            json={"email": "custom-cookie@example.com", "password": "correct horse battery staple"},
        )
        assert relogin_response.status_code == 200
        assert "numra_custom_session" in relogin_response.cookies

        delete_response = await custom_client.post(
            "/v1/account/delete-all",
            json={"password": "correct horse battery staple"},
            headers={"x-csrf-token": custom_client.cookies["numra_csrf"]},
        )
        assert delete_response.status_code == 204

        me_after_delete = await custom_client.get("/v1/auth/me")
        assert me_after_delete.status_code == 401


async def test_login_wrong_password_rejected(client, sessionmaker) -> None:
    await _seed_user(sessionmaker, "wrong@example.com", "correct-password")
    response = await client.post(
        "/v1/auth/login", json={"email": "wrong@example.com", "password": "incorrect-password"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


async def test_self_signup_disabled_by_default(client) -> None:
    response = await client.post(
        "/v1/auth/register", json={"email": "new@example.com", "password": "whatever12345"}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "SELF_SIGNUP_DISABLED"


async def test_unauthenticated_request_rejected(client) -> None:
    response = await client.get("/v1/people")
    assert response.status_code == 401


async def test_logout_requires_csrf(client, sessionmaker) -> None:
    await _seed_user(sessionmaker, "logout-csrf@example.com", "correct horse battery staple")
    await client.post(
        "/v1/auth/login",
        json={"email": "logout-csrf@example.com", "password": "correct horse battery staple"},
    )
    response = await client.post("/v1/auth/logout")  # no x-csrf-token header
    assert response.status_code == 403
    assert response.json()["code"] == "CSRF_VALIDATION_FAILED"

    # The session must still be valid -- logout without CSRF must not have any effect.
    me_response = await client.get("/v1/auth/me")
    assert me_response.status_code == 200


async def test_register_rejects_password_shorter_than_12_chars(settings, db_engine) -> None:
    """Body-schema validation (RegisterRequest.password: Field(min_length=12)) runs
    before the route body, so this must reject even with self-signup enabled --
    isolate that combination via a dedicated app instance rather than the shared
    `client` fixture (which uses the default ALLOW_SELF_SIGNUP=false)."""
    from httpx import ASGITransport, AsyncClient

    from numra_api.app import create_app
    from numra_api.config import Settings
    from numra_api.db import build_sessionmaker

    open_settings = Settings(
        database_url=settings.database_url, environment="test", allow_self_signup=True
    )
    app = create_app(settings=open_settings)
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as open_client:
        too_short = await open_client.post(
            "/v1/auth/register", json={"email": "short-pw@example.com", "password": "short1"}
        )
        assert too_short.status_code == 422

        long_enough = await open_client.post(
            "/v1/auth/register",
            json={"email": "long-enough@example.com", "password": "long-enough-password"},
        )
        assert long_enough.status_code == 201


async def test_register_rejects_role_field_as_privilege_escalation_attempt(
    settings, db_engine
) -> None:
    """RegisterRequest's `extra="forbid"` must reject any body containing an
    unexpected privileged key -- a freshly registered user must always end up
    role=USER, never able to self-elevate via the register body."""
    from httpx import ASGITransport, AsyncClient

    from numra_api.app import create_app
    from numra_api.config import Settings
    from numra_api.db import build_sessionmaker

    open_settings = Settings(
        database_url=settings.database_url, environment="test", allow_self_signup=True
    )
    app = create_app(settings=open_settings)
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as open_client:
        escalation_attempt = await open_client.post(
            "/v1/auth/register",
            json={
                "email": "wannabe-admin@example.com",
                "password": "long-enough-password",
                "role": "ADMIN",
            },
        )
        assert escalation_attempt.status_code == 422

        legit_register = await open_client.post(
            "/v1/auth/register",
            json={"email": "legit-user@example.com", "password": "long-enough-password"},
        )
        assert legit_register.status_code == 201
        assert legit_register.json()["role"] == "USER"

        login_response = await open_client.post(
            "/v1/auth/login",
            json={"email": "legit-user@example.com", "password": "long-enough-password"},
        )
        assert login_response.status_code == 200

        me_response = await open_client.get("/v1/auth/me")
        assert me_response.status_code == 200
        assert me_response.json()["role"] == "USER"
        assert me_response.json()["is_active"] is True


async def test_login_is_rate_limited_per_ip(client, sessionmaker) -> None:
    """P1 hardening: brute-force protection on /v1/auth/login (limit=10/60s per IP,
    see routes/auth.py). All 11 requests hit the same key here since ASGITransport
    reports a fixed client IP for every request in-process."""
    await _seed_user(sessionmaker, "rate-limited@example.com", "correct horse battery staple")

    for _ in range(10):
        response = await client.post(
            "/v1/auth/login",
            json={"email": "rate-limited@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401  # wrong password, but not yet rate-limited

    blocked = await client.post(
        "/v1/auth/login",
        json={"email": "rate-limited@example.com", "password": "wrong-password"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMIT_EXCEEDED"
    assert int(blocked.headers["retry-after"]) > 0

    # Even the CORRECT password is rejected once the limit is exhausted -- the limiter
    # runs as a dependency before the route body, so it blocks every request equally.
    still_blocked = await client.post(
        "/v1/auth/login",
        json={"email": "rate-limited@example.com", "password": "correct horse battery staple"},
    )
    assert still_blocked.status_code == 429
