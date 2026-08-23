from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.models.enums import UserRole
from numra_api.repositories.users import create_user, set_user_role

pytestmark = pytest.mark.integration

ADMIN_ROUTES = [
    ("GET", "/v1/admin/stats"),
    ("GET", "/v1/admin/users"),
    ("GET", "/v1/admin/audit"),
]


async def _seed_user(sessionmaker, email: str, password: str, *, role: UserRole = UserRole.USER):
    async with sessionmaker() as db:
        user = await create_user(db, email=email, password_hash=hash_password(password))
        if role != UserRole.USER:
            await set_user_role(db, user=user, role=role)
        await db.commit()
        return user


async def _login(client, email: str, password: str) -> None:
    response = await client.post("/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


async def test_unauthenticated_gets_401_on_admin_routes(client) -> None:
    for method, path in ADMIN_ROUTES:
        response = await client.request(method, path)
        assert response.status_code == 401


async def test_non_admin_gets_403_on_admin_routes(client, sessionmaker) -> None:
    await _seed_user(sessionmaker, "regular@example.com", "correct horse battery staple")
    await _login(client, "regular@example.com", "correct horse battery staple")

    for method, path in ADMIN_ROUTES:
        response = await client.request(method, path)
        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"


async def test_admin_gets_200_on_admin_routes(client, sessionmaker) -> None:
    await _seed_user(
        sessionmaker, "admin@example.com", "correct horse battery staple", role=UserRole.ADMIN
    )
    await _login(client, "admin@example.com", "correct horse battery staple")

    for method, path in ADMIN_ROUTES:
        response = await client.request(method, path)
        assert response.status_code == 200
