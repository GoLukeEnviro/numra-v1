from __future__ import annotations

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


async def _login(client, sessionmaker, email: str) -> dict:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _create_link_invitation(client, headers) -> dict:
    response = await client.post(
        "/v1/connections/invitations", json={"method": "LINK"}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


async def test_foreign_user_cannot_revoke_others_invitation(client, sessionmaker) -> None:
    headers_a = await _login(client, sessionmaker, "idor-conn-a@example.com")
    invitation = await _create_link_invitation(client, headers_a)

    await client.post("/v1/auth/logout")
    headers_c = await _login(client, sessionmaker, "idor-conn-c@example.com")

    response = await client.post(
        f"/v1/connections/invitations/{invitation['id']}/revoke", headers=headers_c
    )
    assert response.status_code == 404
    assert response.json()["code"] == "INVITATION_NOT_FOUND"


async def test_foreign_user_cannot_list_others_invitations(client, sessionmaker) -> None:
    headers_a = await _login(client, sessionmaker, "idor-conn-list-a@example.com")
    await _create_link_invitation(client, headers_a)

    await client.post("/v1/auth/logout")
    headers_c = await _login(client, sessionmaker, "idor-conn-list-c@example.com")

    response = await client.get("/v1/connections/invitations", headers=headers_c)
    assert response.status_code == 200
    assert response.json() == []


async def test_foreign_user_cannot_dissolve_others_connection(client, sessionmaker) -> None:
    headers_a = await _login(client, sessionmaker, "idor-conn-dis-a@example.com")
    invitation = await _create_link_invitation(client, headers_a)
    await client.post("/v1/auth/logout")
    headers_b = await _login(client, sessionmaker, "idor-conn-dis-b@example.com")
    redeem = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_b,
    )
    connection_id = redeem.json()["connection"]["id"]

    await client.post("/v1/auth/logout")
    headers_c = await _login(client, sessionmaker, "idor-conn-dis-c@example.com")

    response = await client.post(f"/v1/connections/{connection_id}/dissolve", headers=headers_c)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


async def test_foreign_user_cannot_see_others_connections(client, sessionmaker) -> None:
    headers_a = await _login(client, sessionmaker, "idor-conn-see-a@example.com")
    invitation = await _create_link_invitation(client, headers_a)
    await client.post("/v1/auth/logout")
    headers_b = await _login(client, sessionmaker, "idor-conn-see-b@example.com")
    await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_b,
    )

    await client.post("/v1/auth/logout")
    headers_c = await _login(client, sessionmaker, "idor-conn-see-c@example.com")
    response = await client.get("/v1/connections", headers=headers_c)
    assert response.status_code == 200
    assert response.json() == []


async def test_invalid_token_redeem_returns_expired_or_invalid(client, sessionmaker) -> None:
    headers = await _login(client, sessionmaker, "idor-conn-invalid-token@example.com")
    response = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": "totally-bogus-token-value"},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVITATION_EXPIRED_OR_INVALID"


async def test_preview_invalid_token_returns_not_found(client) -> None:
    response = await client.get("/v1/connections/invitations/redeem/does-not-exist")
    assert response.status_code == 404
