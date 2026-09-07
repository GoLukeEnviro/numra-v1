from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select

from numra_api.auth.passwords import hash_password
from numra_api.auth.tokens import hash_token
from numra_api.models import (
    ConnectionInvitation,
    ConsentGrant,
    RelationshipWorkspace,
    WorkspaceMember,
)
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


async def _signup(client, sessionmaker, email: str) -> dict:
    """Creates the user and logs in -- use once per email. See `_switch_user` to
    re-activate an already-created user's session (the test `client` fixture has one
    shared cookie jar, so only one user is "logged in" at a time)."""
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    return await _switch_user(client, email)


async def _switch_user(client, email: str) -> dict:
    await client.post("/v1/auth/logout")
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


async def test_connection_happy_path_link_invite(client, sessionmaker) -> None:
    headers_a = await _signup(client, sessionmaker, "conn-a@example.com")
    invitation = await _create_link_invitation(client, headers_a)

    headers_b = await _signup(client, sessionmaker, "conn-b@example.com")

    preview = await client.get(f"/v1/connections/invitations/redeem/{invitation['token']}")
    assert preview.status_code == 200
    assert preview.json()["method"] == "LINK"

    redeem = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_b,
    )
    assert redeem.status_code == 201
    body = redeem.json()
    workspace_id = body["workspace_id"]
    connection = body["connection"]
    assert connection["status"] == "ACTIVE"

    async with sessionmaker() as db:
        members = (
            (
                await db.execute(
                    select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(members) == 2

        grants = (
            (
                await db.execute(
                    select(ConsentGrant).where(ConsentGrant.workspace_id == workspace_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(grants) == 6
        scopes = {g.scope for g in grants}
        assert scopes == {"CORE_NUMEROLOGY", "RELATIONSHIP_INSIGHTS", "CURRENT_TIMING"}

        workspaces = (
            (
                await db.execute(
                    select(RelationshipWorkspace).where(RelationshipWorkspace.id == workspace_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(workspaces) == 1


async def test_code_and_email_invite_methods(client, sessionmaker) -> None:
    headers = await _signup(client, sessionmaker, "conn-methods@example.com")

    code_response = await client.post(
        "/v1/connections/invitations", json={"method": "CODE"}, headers=headers
    )
    assert code_response.status_code == 201

    email_response = await client.post(
        "/v1/connections/invitations",
        json={"method": "EMAIL", "invitee_email": "someone-else@example.com"},
        headers=headers,
    )
    assert email_response.status_code == 201
    assert email_response.json()["invitee_email"] == "someone-else@example.com"


async def test_email_invite_anti_enumeration_identical_response(client, sessionmaker) -> None:
    headers = await _signup(client, sessionmaker, "conn-anti-enum@example.com")

    registered_response = await client.post(
        "/v1/connections/invitations",
        json={"method": "EMAIL", "invitee_email": "conn-anti-enum-registered@example.com"},
        headers=headers,
    )
    unregistered_response = await client.post(
        "/v1/connections/invitations",
        json={"method": "EMAIL", "invitee_email": "definitely-not-registered@example.com"},
        headers=headers,
    )
    assert registered_response.status_code == unregistered_response.status_code == 201
    assert set(registered_response.json().keys()) == set(unregistered_response.json().keys())


async def test_expired_invitation_cannot_be_redeemed(client, sessionmaker) -> None:
    headers_a = await _signup(client, sessionmaker, "conn-expired-a@example.com")
    invitation = await _create_link_invitation(client, headers_a)

    async with sessionmaker() as db:
        row = (
            await db.execute(
                select(ConnectionInvitation).where(
                    ConnectionInvitation.token_hash == hash_token(invitation["token"])
                )
            )
        ).scalar_one()
        row.expires_at = dt.datetime.now(dt.UTC) - dt.timedelta(days=1)
        await db.commit()

    headers_b = await _signup(client, sessionmaker, "conn-expired-b@example.com")

    response = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_b,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVITATION_EXPIRED_OR_INVALID"


async def test_revoked_invitation_cannot_be_redeemed(client, sessionmaker) -> None:
    headers_a = await _signup(client, sessionmaker, "conn-revoked-a@example.com")
    invitation = await _create_link_invitation(client, headers_a)

    revoke_response = await client.post(
        f"/v1/connections/invitations/{invitation['id']}/revoke", headers=headers_a
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["state"] == "REVOKED"

    headers_b = await _signup(client, sessionmaker, "conn-revoked-b@example.com")

    response = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_b,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVITATION_EXPIRED_OR_INVALID"


async def test_duplicate_redeem_of_same_invitation_fails(client, sessionmaker) -> None:
    headers_a = await _signup(client, sessionmaker, "conn-dup-redeem-a@example.com")
    invitation = await _create_link_invitation(client, headers_a)

    headers_b = await _signup(client, sessionmaker, "conn-dup-redeem-b@example.com")
    first = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_b,
    )
    assert first.status_code == 201

    headers_c = await _signup(client, sessionmaker, "conn-dup-redeem-c@example.com")
    second = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_c,
    )
    assert second.status_code == 400
    assert second.json()["code"] == "INVITATION_EXPIRED_OR_INVALID"


async def test_duplicate_connection_between_same_users_rejected(client, sessionmaker) -> None:
    email_a = "conn-dup-a@example.com"
    email_b = "conn-dup-b@example.com"

    headers_a = await _signup(client, sessionmaker, email_a)
    invitation_1 = await _create_link_invitation(client, headers_a)
    headers_b = await _signup(client, sessionmaker, email_b)
    first = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation_1["token"]},
        headers=headers_b,
    )
    assert first.status_code == 201

    headers_a = await _switch_user(client, email_a)
    invitation_2 = await _create_link_invitation(client, headers_a)
    headers_b = await _switch_user(client, email_b)
    second = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation_2["token"]},
        headers=headers_b,
    )
    assert second.status_code == 409
    assert second.json()["code"] == "CONNECTION_ALREADY_EXISTS"


async def test_self_invite_email_rejected(client, sessionmaker) -> None:
    headers = await _signup(client, sessionmaker, "conn-self@example.com")
    response = await client.post(
        "/v1/connections/invitations",
        json={"method": "EMAIL", "invitee_email": "conn-self@example.com"},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "CANNOT_INVITE_SELF"


async def test_self_redeem_of_own_invitation_rejected(client, sessionmaker) -> None:
    headers = await _signup(client, sessionmaker, "conn-self-redeem@example.com")
    invitation = await _create_link_invitation(client, headers)

    response = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "CANNOT_INVITE_SELF"


async def test_dissolve_connection(client, sessionmaker) -> None:
    headers_a = await _signup(client, sessionmaker, "conn-dissolve-a@example.com")
    invitation = await _create_link_invitation(client, headers_a)
    headers_b = await _signup(client, sessionmaker, "conn-dissolve-b@example.com")
    redeem = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_b,
    )
    connection_id = redeem.json()["connection"]["id"]

    dissolve = await client.post(f"/v1/connections/{connection_id}/dissolve", headers=headers_b)
    assert dissolve.status_code == 200
    assert dissolve.json()["status"] == "DISSOLVED"


async def test_addressed_invitee_can_decline_email_invitation(client, sessionmaker) -> None:
    headers_a = await _signup(client, sessionmaker, "conn-decline-a@example.com")
    invite = await client.post(
        "/v1/connections/invitations",
        json={"method": "EMAIL", "invitee_email": "conn-decline-b@example.com"},
        headers=headers_a,
    )
    invitation_id = invite.json()["id"]

    headers_b = await _signup(client, sessionmaker, "conn-decline-b@example.com")
    decline = await client.post(
        f"/v1/connections/invitations/{invitation_id}/decline", headers=headers_b
    )
    assert decline.status_code == 200
    assert decline.json()["state"] == "DECLINED"


async def test_unaddressed_user_cannot_decline_foreign_invitation(client, sessionmaker) -> None:
    """Regression: decline_own_invitation previously accepted any authenticated user's
    id-only request, letting a stranger DoS/inspect a foreign invitation. Neither a
    LINK invite (no invitee identity at all) nor an EMAIL invite addressed to someone
    else may be declined by an unrelated authenticated user."""
    headers_a = await _signup(client, sessionmaker, "conn-decline-link-a@example.com")
    link_invite = await _create_link_invitation(client, headers_a)
    email_invite = await client.post(
        "/v1/connections/invitations",
        json={"method": "EMAIL", "invitee_email": "conn-decline-real-target@example.com"},
        headers=headers_a,
    )

    headers_stranger = await _signup(client, sessionmaker, "conn-decline-stranger@example.com")

    async with sessionmaker() as db:
        link_invitation_id = (
            await db.execute(
                select(ConnectionInvitation.id).where(
                    ConnectionInvitation.token_hash == hash_token(link_invite["token"])
                )
            )
        ).scalar_one()

    link_decline = await client.post(
        f"/v1/connections/invitations/{link_invitation_id}/decline", headers=headers_stranger
    )
    assert link_decline.status_code == 404

    email_decline = await client.post(
        f"/v1/connections/invitations/{email_invite.json()['id']}/decline",
        headers=headers_stranger,
    )
    assert email_decline.status_code == 404
