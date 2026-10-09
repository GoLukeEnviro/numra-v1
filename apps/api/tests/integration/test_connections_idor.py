from __future__ import annotations

import datetime as dt

import pytest

from numra_api.auth.passwords import hash_password
from numra_api.repositories.users import create_user, get_user_by_email, mark_email_verified

pytestmark = pytest.mark.integration


async def _login(client, sessionmaker, email: str, *, verified: bool = True) -> dict:
    async with sessionmaker() as db:
        user = await create_user(db, email=email, password_hash=hash_password("password12345"))
        if verified:
            await mark_email_verified(db, user=user, verified_at=dt.datetime.now(dt.UTC))
        await db.commit()
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _verify_email(sessionmaker, email: str) -> None:
    async with sessionmaker() as db:
        user = await get_user_by_email(db, email=email)
        assert user is not None
        await mark_email_verified(db, user=user, verified_at=dt.datetime.now(dt.UTC))
        await db.commit()


async def _create_link_invitation(client, headers) -> dict:
    response = await client.post(
        "/v1/connections/invitations", json={"method": "LINK"}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


async def _create_email_invitation(client, headers, invitee_email: str) -> dict:
    response = await client.post(
        "/v1/connections/invitations",
        json={"method": "EMAIL", "invitee_email": invitee_email},
        headers=headers,
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


async def test_email_invitation_cannot_be_redeemed_by_wrong_account(client, sessionmaker) -> None:
    """A3: the EMAIL invitation addressed to bob@ must not be redeemable by mallory@,
    even with a valid, unexpired token -- the token alone isn't the whole claim."""
    headers_a = await _login(client, sessionmaker, "idor-email-a@example.com")
    invitation = await _create_email_invitation(client, headers_a, "idor-email-bob@example.com")

    headers_mallory = await _login(client, sessionmaker, "idor-email-mallory@example.com")

    response = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_mallory,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVITATION_EXPIRED_OR_INVALID"

    # The rejected attempt must not have burned the invitation for the real invitee.
    headers_bob = await _login(client, sessionmaker, "idor-email-bob@example.com")
    retry = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_bob,
    )
    assert retry.status_code == 201


async def test_email_invitation_requires_verified_email_to_redeem(client, sessionmaker) -> None:
    """A3: matching the invitee email alone isn't proof of mailbox control -- the
    redeeming account must also have verified that address."""
    headers_a = await _login(client, sessionmaker, "idor-email-verify-a@example.com")
    invitation = await _create_email_invitation(
        client, headers_a, "idor-email-verify-bob@example.com"
    )

    headers_bob = await _login(
        client, sessionmaker, "idor-email-verify-bob@example.com", verified=False
    )
    unverified_attempt = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_bob,
    )
    assert unverified_attempt.status_code == 403
    assert unverified_attempt.json()["code"] == "EMAIL_VERIFICATION_REQUIRED"

    await _verify_email(sessionmaker, "idor-email-verify-bob@example.com")
    verified_attempt = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_bob,
    )
    assert verified_attempt.status_code == 201


async def test_unverified_user_gets_404_on_foreign_connection_and_workspace(
    client, sessionmaker
) -> None:
    """Fehlende Verifizierung oeffnet keine fremden Daten: derselbe 404 wie fuer ein
    verifiziertes fremdes Konto."""
    headers_a = await _login(client, sessionmaker, "idor-unver-a@example.com")
    invitation = await _create_link_invitation(client, headers_a)
    await client.post("/v1/auth/logout")
    headers_b = await _login(client, sessionmaker, "idor-unver-b@example.com")
    redeem = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_b,
    )
    connection_id = redeem.json()["connection"]["id"]
    workspace_id = redeem.json()["workspace_id"]

    await client.post("/v1/auth/logout")
    headers_c = await _login(client, sessionmaker, "idor-unver-c@example.com", verified=False)

    dissolve = await client.post(f"/v1/connections/{connection_id}/dissolve", headers=headers_c)
    assert dissolve.status_code == 404
    workspace = await client.get(f"/v1/workspaces/{workspace_id}", headers=headers_c)
    assert workspace.status_code == 404
    assert (await client.get("/v1/connections", headers=headers_c)).json() == []
