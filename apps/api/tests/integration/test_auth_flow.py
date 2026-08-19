from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
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

    logout_response = await client.post("/v1/auth/logout")
    assert logout_response.status_code == 204

    me_after_logout = await client.get("/v1/auth/me")
    assert me_after_logout.status_code == 401
    assert me_after_logout.json()["code"] == "NOT_AUTHENTICATED"


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
