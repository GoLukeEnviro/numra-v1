from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user, set_user_active

pytestmark = pytest.mark.integration


async def _seed_user(sessionmaker, email: str, password: str):
    async with sessionmaker() as db:
        user = await create_user(db, email=email, password_hash=hash_password(password))
        await db.commit()
        return user


async def test_disabled_user_login_matches_wrong_password_shape(client, sessionmaker) -> None:
    """Explicit anti-enumeration assertion: a disabled account's login rejection must
    be byte-identical to a wrong-password rejection -- both INVALID_CREDENTIALS, 401,
    same message shape."""
    user = await _seed_user(sessionmaker, "disabled1@example.com", "correct horse battery staple")
    async with sessionmaker() as db:
        db_user = await db.get(type(user), user.id)
        await set_user_active(db, user=db_user, is_active=False)
        await db.commit()

    disabled_response = await client.post(
        "/v1/auth/login",
        json={"email": "disabled1@example.com", "password": "correct horse battery staple"},
    )

    wrong_password_response = await client.post(
        "/v1/auth/login",
        json={"email": "someone-else-entirely@example.com", "password": "whatever-wrong"},
    )

    assert disabled_response.status_code == wrong_password_response.status_code == 401
    assert disabled_response.json() == wrong_password_response.json()
    assert disabled_response.json()["code"] == "INVALID_CREDENTIALS"


async def test_disabled_mid_session_rejects_next_request(client, sessionmaker) -> None:
    await _seed_user(sessionmaker, "disabled2@example.com", "correct horse battery staple")

    login_response = await client.post(
        "/v1/auth/login",
        json={"email": "disabled2@example.com", "password": "correct horse battery staple"},
    )
    assert login_response.status_code == 200

    me_before = await client.get("/v1/auth/me")
    assert me_before.status_code == 200

    async with sessionmaker() as db:
        from numra_api.repositories.users import get_user_by_email

        db_user = await get_user_by_email(db, email="disabled2@example.com")
        await set_user_active(db, user=db_user, is_active=False)
        await db.commit()

    me_after = await client.get("/v1/auth/me")
    assert me_after.status_code == 401
    assert me_after.json()["code"] == "NOT_AUTHENTICATED"
