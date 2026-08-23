from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.models.enums import UserRole
from numra_api.repositories.users import create_user, set_user_role

pytestmark = pytest.mark.integration


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


async def test_users_list_never_leaks_password_hash(client, sessionmaker) -> None:
    await _seed_user(
        sessionmaker, "listadmin@example.com", "correct horse battery staple", role=UserRole.ADMIN
    )
    await _seed_user(sessionmaker, "other@example.com", "correct horse battery staple")
    await _login(client, "listadmin@example.com", "correct horse battery staple")

    response = await client.get("/v1/admin/users")
    assert response.status_code == 200
    body = response.json()
    raw = str(body)
    assert "password_hash" not in raw
    assert "correct horse battery staple" not in raw
    for item in body["items"]:
        assert set(item.keys()) == {
            "id",
            "email",
            "role",
            "is_active",
            "created_at",
            "last_login_at",
            "active_session_count",
            "people_count",
            "calculation_count",
            "report_count",
            "relationship_count",
        }


async def test_users_list_pagination_and_search(client, sessionmaker) -> None:
    await _seed_user(
        sessionmaker, "pageadmin@example.com", "correct horse battery staple", role=UserRole.ADMIN
    )
    for i in range(3):
        await _seed_user(sessionmaker, f"findme{i}@example.com", "correct horse battery staple")
    await _seed_user(sessionmaker, "unrelated@example.com", "correct horse battery staple")
    await _login(client, "pageadmin@example.com", "correct horse battery staple")

    response = await client.get("/v1/admin/users", params={"search": "findme", "page_size": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2

    page2 = await client.get(
        "/v1/admin/users", params={"search": "findme", "page": 2, "page_size": 2}
    )
    assert page2.status_code == 200
    assert len(page2.json()["items"]) == 1


async def test_users_list_does_not_leak_other_users_person_data(client, sessionmaker) -> None:
    await _seed_user(
        sessionmaker, "peekadmin@example.com", "correct horse battery staple", role=UserRole.ADMIN
    )
    await _login(client, "peekadmin@example.com", "correct horse battery staple")

    response = await client.get("/v1/admin/users")
    assert response.status_code == 200
    for item in response.json()["items"]:
        # Only aggregate counts are exposed -- no nested person/report objects.
        assert isinstance(item["people_count"], int)
        assert "people" not in item
        assert "reports" not in item
