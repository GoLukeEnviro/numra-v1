from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration

PASSWORD = "correct horse battery staple"


async def _seed_user(sessionmaker, email: str) -> None:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password(PASSWORD))
        await db.commit()


async def test_mobile_login_me_logout_flow_uses_one_time_bearer_token(client, sessionmaker) -> None:
    await _seed_user(sessionmaker, "mobile@example.com")

    login = await client.post(
        "/v1/auth/mobile/login", json={"email": "mobile@example.com", "password": PASSWORD}
    )
    assert login.status_code == 200
    payload = login.json()
    assert payload["token_type"] == "Bearer"
    assert len(payload["access_token"]) >= 32
    assert payload["user"]["email"] == "mobile@example.com"
    assert login.headers["cache-control"] == "no-store"
    assert "numra_session" not in login.cookies
    assert "numra_csrf" not in login.cookies

    headers = {"Authorization": f"Bearer {payload['access_token']}"}
    me = await client.get("/v1/auth/mobile/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "mobile@example.com"

    logout = await client.post("/v1/auth/mobile/logout", headers=headers)
    assert logout.status_code == 204
    assert (await client.get("/v1/auth/mobile/me", headers=headers)).status_code == 401


@pytest.mark.parametrize(
    "authorization", [None, "Basic abc", "Bearer", "Bearer ", "Bearer invalid-token"]
)
async def test_mobile_bearer_rejects_missing_malformed_and_unknown_tokens(
    client, authorization
) -> None:
    headers = {} if authorization is None else {"Authorization": authorization}
    response = await client.get("/v1/auth/mobile/me", headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"


async def test_mobile_login_preserves_generic_invalid_credentials_shape(
    client, sessionmaker
) -> None:
    await _seed_user(sessionmaker, "mobile-wrong@example.com")
    response = await client.post(
        "/v1/auth/mobile/login",
        json={"email": "mobile-wrong@example.com", "password": "wrong"},
    )
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"
