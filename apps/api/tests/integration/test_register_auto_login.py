from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from numra_api.app import create_app
from numra_api.auth.passwords import hash_password
from numra_api.config import Settings
from numra_api.db import build_sessionmaker
from numra_api.models import User
from numra_api.models.enums import UserRole
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration

PASSWORD = "long-enough-password"


def _open_signup_client(settings: Settings, db_engine) -> AsyncClient:
    """A dedicated app with ALLOW_SELF_SIGNUP=true (the shared `client` fixture is
    built with the default false). A fresh app also means a fresh in-memory rate
    limiter, so each test starts with the full 5-registrations-per-hour budget."""
    app = create_app(
        settings=Settings(
            database_url=settings.database_url, environment="test", allow_self_signup=True
        )
    )
    app.state.engine = db_engine
    app.state.sessionmaker = build_sessionmaker(db_engine)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def test_register_rejected_when_self_signup_disabled(client) -> None:
    response = await client.post(
        "/v1/auth/register", json={"email": "closed@example.com", "password": PASSWORD}
    )

    assert response.status_code == 403
    assert response.json()["code"] == "SELF_SIGNUP_DISABLED"


async def test_register_signs_the_new_user_straight_in(settings: Settings, db_engine) -> None:
    """V1.6 B: registration no longer leaves the caller anonymous -- it issues the same
    session + CSRF cookies as `login`, so the very next request is authenticated."""
    async with _open_signup_client(settings, db_engine) as signup_client:
        response = await signup_client.post(
            "/v1/auth/register", json={"email": "fresh@example.com", "password": PASSWORD}
        )

        assert response.status_code == 201
        assert response.json()["email"] == "fresh@example.com"
        assert response.json()["role"] == "USER"
        assert response.json()["is_active"] is True
        assert "numra_session" in response.cookies
        assert "numra_csrf" in response.cookies

        me_response = await signup_client.get("/v1/auth/me")
        assert me_response.status_code == 200
        assert me_response.json()["email"] == "fresh@example.com"
        assert me_response.json()["role"] == "USER"
        assert me_response.json()["is_active"] is True


@pytest.mark.parametrize(
    "privileged_key,privileged_value",
    [
        ("role", "ADMIN"),
        ("is_admin", True),
        ("is_active", False),
        ("permissions", ["admin:all"]),
    ],
)
async def test_register_rejects_privileged_payload_keys(
    settings: Settings, db_engine, sessionmaker, privileged_key: str, privileged_value: object
) -> None:
    """`RegisterRequest`'s `extra="forbid"` must turn every privilege-shaped key into a
    422 -- silently ignoring one would still create the account, and an account created
    from an attacker-controlled body is exactly what must never exist."""
    async with _open_signup_client(settings, db_engine) as signup_client:
        response = await signup_client.post(
            "/v1/auth/register",
            json={
                "email": "escalation@example.com",
                "password": PASSWORD,
                privileged_key: privileged_value,
            },
        )

    assert response.status_code == 422

    async with sessionmaker() as db:
        users = list((await db.execute(select(User))).scalars().all())
    assert users == []


async def test_register_rejects_duplicate_email_regardless_of_casing(
    settings: Settings, db_engine
) -> None:
    """`Foo@Example.com` and `foo@example.com` are one identity -- the second signup
    must fail with the application error, never with a raw DB constraint violation."""
    async with _open_signup_client(settings, db_engine) as signup_client:
        first = await signup_client.post(
            "/v1/auth/register", json={"email": "Foo@Example.com", "password": PASSWORD}
        )
        assert first.status_code == 201
        assert first.json()["email"] == "foo@example.com"

        duplicate = await signup_client.post(
            "/v1/auth/register", json={"email": "foo@example.com", "password": PASSWORD}
        )

    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "EMAIL_ALREADY_REGISTERED"


async def test_login_accepts_a_different_casing_than_registration(
    settings: Settings, db_engine
) -> None:
    async with _open_signup_client(settings, db_engine) as signup_client:
        registered = await signup_client.post(
            "/v1/auth/register", json={"email": "Mixed.Case@Example.com", "password": PASSWORD}
        )
        assert registered.status_code == 201

        login_response = await signup_client.post(
            "/v1/auth/login", json={"email": "MIXED.CASE@EXAMPLE.COM", "password": PASSWORD}
        )

    assert login_response.status_code == 200
    assert login_response.json()["email"] == "mixed.case@example.com"


async def test_existing_login_logout_flow_is_unchanged(client, sessionmaker) -> None:
    """Regression guard for the extracted `_issue_authenticated_session` helper: the
    login path must behave exactly as before the register route started sharing it."""
    async with sessionmaker() as db:
        await create_user(db, email="regression@example.com", password_hash=hash_password(PASSWORD))
        await db.commit()

    login_response = await client.post(
        "/v1/auth/login", json={"email": "regression@example.com", "password": PASSWORD}
    )
    assert login_response.status_code == 200
    assert "numra_session" in login_response.cookies
    assert "numra_csrf" in login_response.cookies
    assert login_response.json()["role"] == str(UserRole.USER)

    me_response = await client.get("/v1/auth/me")
    assert me_response.status_code == 200

    logout_response = await client.post(
        "/v1/auth/logout", headers={"x-csrf-token": client.cookies["numra_csrf"]}
    )
    assert logout_response.status_code == 204
    assert (await client.get("/v1/auth/me")).status_code == 401
