"""PR-V2-10 -- Dissolution: kaskadierender Consent-Revoke, Retain-Read-Only-
Enforcement und Idempotenz (services/connection_service.py::dissolve_own_connection,
services/workspace_guard.py). Nutzt das `_connect`-Zwei-User-Muster aus
test_workspace_tasks.py / test_checkins.py.

Leitplanke für jeden 409-Test hier: der Guard MUSS hinter dem Membership-Gate sitzen.
`test_dissolve_idor_third_user_gets_404` ist der Gegenbeweis -- ein Fremder bekommt nie
den 409, der die Existenz des Workspace verraten würde.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from numra_api.auth.passwords import hash_password
from numra_api.models import ConsentEvent, ConsentGrant, RelationshipWorkspace
from numra_api.repositories.users import create_user

pytestmark = pytest.mark.integration


async def _signup(client, sessionmaker, email: str) -> dict:
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


async def _connect(client, sessionmaker, email_a: str, email_b: str) -> tuple[str, str]:
    """Returns (workspace_id, connection_id); leaves the active session as user B."""
    headers_a = await _signup(client, sessionmaker, email_a)
    invitation = (
        await client.post("/v1/connections/invitations", json={"method": "LINK"}, headers=headers_a)
    ).json()
    headers_b = await _signup(client, sessionmaker, email_b)
    redeem = await client.post(
        "/v1/connections/invitations/redeem",
        json={"token": invitation["token"]},
        headers=headers_b,
    )
    assert redeem.status_code == 201
    body = redeem.json()
    return body["workspace_id"], body["connection"]["id"]


async def _dissolve(client, connection_id: str, headers: dict) -> dict:
    response = await client.post(f"/v1/connections/{connection_id}/dissolve", headers=headers)
    assert response.status_code == 200
    return response.json()


async def _create_self_person(client, headers: dict, payload: dict) -> None:
    person = await client.post("/v1/people", json=payload, headers=headers)
    assert person.status_code == 201
    calc = await client.post(
        f"/v1/people/{person.json()['id']}/calculations",
        json={"as_of_date": "2026-08-19"},
        headers=headers,
    )
    assert calc.status_code == 201


async def _set_up_partner_workspace(
    client, sessionmaker, lukas_payload, email_a: str, email_b: str
) -> tuple[str, str]:
    """Beide Seiten mit SELF-Profil + Calculation, `relationship_type=PARTNER` -- die
    Vorbedingung, die ein Analysis-Job braucht (siehe test_relationship_analysis.py)."""
    workspace_id, connection_id = await _connect(client, sessionmaker, email_a, email_b)

    headers_b = await _switch_user(client, email_b)
    await _create_self_person(client, headers_b, {**lukas_payload, "birth_date": "1990-03-14"})
    headers_a = await _switch_user(client, email_a)
    await _create_self_person(
        client,
        headers_a,
        {
            **lukas_payload,
            "birth_first_names": "Partner",
            "birth_last_name": "Eins",
            "birth_date": "1988-07-22",
        },
    )
    patch = await client.patch(
        f"/v1/workspaces/{workspace_id}",
        json={"relationship_type": "PARTNER"},
        headers=headers_a,
    )
    assert patch.status_code == 200
    return workspace_id, connection_id


# ---------------------------------------------------------------------------
# Kaskadierender Consent-Revoke
# ---------------------------------------------------------------------------


async def test_dissolve_revokes_every_grant_and_writes_one_event_each(client, sessionmaker) -> None:
    workspace_id, connection_id = await _connect(
        client, sessionmaker, "dis-cascade-a@example.com", "dis-cascade-b@example.com"
    )
    headers_b = await _switch_user(client, "dis-cascade-b@example.com")

    async with sessionmaker() as db:
        active_before = (
            await db.execute(
                select(func.count())
                .select_from(ConsentGrant)
                .where(ConsentGrant.workspace_id == workspace_id, ConsentGrant.revoked_at.is_(None))
            )
        ).scalar_one()
    assert active_before == 6

    await _dissolve(client, connection_id, headers_b)

    async with sessionmaker() as db:
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
        assert all(g.revoked_at is not None for g in grants)

        revoked_events = (
            (
                await db.execute(
                    select(ConsentEvent).where(
                        ConsentEvent.grant_id.in_([g.id for g in grants]),
                        ConsentEvent.event_type == "REVOKED",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(revoked_events) == 6
        assert {e.grant_id for e in revoked_events} == {g.id for g in grants}

        workspace = (
            await db.execute(
                select(RelationshipWorkspace).where(RelationshipWorkspace.id == workspace_id)
            )
        ).scalar_one()
        assert workspace.status == "DISSOLVED"
        assert workspace.dissolved_at is not None


# ---------------------------------------------------------------------------
# Retain-Read-Only: Schreibpfade sind zu (409)
# ---------------------------------------------------------------------------


async def test_no_new_copilot_message_after_dissolve(client, sessionmaker) -> None:
    """Das 409 muss VOR dem Consent-Gate greifen: nach dem Dissolve sind alle Grants
    revoked, ein zuerst laufender Consent-Check würde stattdessen 403 liefern und die
    eigentliche Ursache verschleiern."""
    workspace_id, connection_id = await _connect(
        client, sessionmaker, "dis-cop-a@example.com", "dis-cop-b@example.com"
    )
    headers_b = await _switch_user(client, "dis-cop-b@example.com")
    thread = await client.post(
        f"/v1/workspaces/{workspace_id}/copilot/threads",
        json={"scope": "RELATIONSHIP_SHARED"},
        headers=headers_b,
    )
    assert thread.status_code in (200, 201)
    thread_id = thread.json()["id"]

    await _dissolve(client, connection_id, headers_b)

    headers_b = await _switch_user(client, "dis-cop-b@example.com")
    post = await client.post(
        f"/v1/workspaces/{workspace_id}/copilot/threads/{thread_id}/messages",
        json={"content": "Wie geht es weiter?"},
        headers=headers_b,
    )
    assert post.status_code == 409
    assert post.json()["code"] == "WORKSPACE_DISSOLVED"

    new_thread = await client.post(
        f"/v1/workspaces/{workspace_id}/copilot/threads",
        json={"scope": "RELATIONSHIP_PRIVATE"},
        headers=headers_b,
    )
    assert new_thread.status_code == 409
    assert new_thread.json()["code"] == "WORKSPACE_DISSOLVED"


async def test_no_new_checkin_after_dissolve(client, sessionmaker) -> None:
    workspace_id, connection_id = await _connect(
        client, sessionmaker, "dis-chk-a@example.com", "dis-chk-b@example.com"
    )
    headers_b = await _switch_user(client, "dis-chk-b@example.com")
    template = await client.get(
        f"/v1/workspaces/{workspace_id}/checkin-template", headers=headers_b
    )
    assert template.status_code == 200
    responses = [
        {"dimension_id": dimension["id"], "value": 7} for dimension in template.json()["dimensions"]
    ]

    await _dissolve(client, connection_id, headers_b)

    headers_b = await _switch_user(client, "dis-chk-b@example.com")
    submit = await client.post(
        f"/v1/workspaces/{workspace_id}/checkins",
        json={"responses": responses},
        headers=headers_b,
    )
    assert submit.status_code == 409
    assert submit.json()["code"] == "WORKSPACE_DISSOLVED"


async def test_no_new_analysis_job_of_either_type_after_dissolve(
    client, sessionmaker, lukas_payload
) -> None:
    workspace_id, connection_id = await _set_up_partner_workspace(
        client, sessionmaker, lukas_payload, "dis-an-a@example.com", "dis-an-b@example.com"
    )
    headers_a = await _switch_user(client, "dis-an-a@example.com")
    await _dissolve(client, connection_id, headers_a)

    headers_a = await _switch_user(client, "dis-an-a@example.com")
    for path in ("relationship-analysis", "shadow-dynamics"):
        response = await client.post(
            f"/v1/workspaces/{workspace_id}/{path}", json={}, headers=headers_a
        )
        assert response.status_code == 409, path
        assert response.json()["code"] == "WORKSPACE_DISSOLVED", path


async def test_no_new_task_or_roadmap_after_dissolve(client, sessionmaker) -> None:
    workspace_id, connection_id = await _connect(
        client, sessionmaker, "dis-tr-a@example.com", "dis-tr-b@example.com"
    )
    headers_b = await _switch_user(client, "dis-tr-b@example.com")
    await _dissolve(client, connection_id, headers_b)

    headers_b = await _switch_user(client, "dis-tr-b@example.com")
    task = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={"task_type": "JOINT_SHARED", "title": "Nach dem Ende"},
        headers=headers_b,
    )
    assert task.status_code == 409
    assert task.json()["code"] == "WORKSPACE_DISSOLVED"

    roadmap = await client.post(
        f"/v1/workspaces/{workspace_id}/roadmaps",
        json={"roadmap_type": "14_DAY", "title": "Nach dem Ende"},
        headers=headers_b,
    )
    assert roadmap.status_code == 409
    assert roadmap.json()["code"] == "WORKSPACE_DISSOLVED"


# ---------------------------------------------------------------------------
# Retain-Read-Only: Lesepfade bleiben offen
# ---------------------------------------------------------------------------


async def test_both_parties_retain_read_access_after_dissolve(
    client, sessionmaker, lukas_payload
) -> None:
    """Kein GET darf durch den Guard laufen -- die gemeinsame Historie bleibt für beide
    Seiten lesbar (specs/v2/dissolution-policy.md)."""
    workspace_id, connection_id = await _set_up_partner_workspace(
        client, sessionmaker, lukas_payload, "dis-read-a@example.com", "dis-read-b@example.com"
    )
    headers_a = await _switch_user(client, "dis-read-a@example.com")
    analysis = await client.post(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", json={}, headers=headers_a
    )
    assert analysis.status_code == 201
    task = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={"task_type": "JOINT_SHARED", "title": "Gemeinsam kochen"},
        headers=headers_a,
    )
    assert task.status_code == 201
    roadmap = await client.post(
        f"/v1/workspaces/{workspace_id}/roadmaps",
        json={"roadmap_type": "14_DAY", "title": "Neustart"},
        headers=headers_a,
    )
    assert roadmap.status_code == 201

    await _dissolve(client, connection_id, headers_a)

    for email in ("dis-read-a@example.com", "dis-read-b@example.com"):
        headers = await _switch_user(client, email)
        overview = await client.get(f"/v1/workspaces/{workspace_id}", headers=headers)
        assert overview.status_code == 200, email
        assert overview.json()["workspace"]["status"] == "DISSOLVED", email

        for path in ("tasks", "roadmaps", "checkins", "shared-reflections"):
            listing = await client.get(f"/v1/workspaces/{workspace_id}/{path}", headers=headers)
            assert listing.status_code == 200, (email, path)

        detail = await client.get(
            f"/v1/workspaces/{workspace_id}/tasks/{task.json()['id']}", headers=headers
        )
        assert detail.status_code == 200, email
        assert detail.json()["title"] == "Gemeinsam kochen"

        roadmap_detail = await client.get(
            f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap.json()['id']}", headers=headers
        )
        assert roadmap_detail.status_code == 200, email

        analysis_read = await client.get(
            f"/v1/workspaces/{workspace_id}/relationship-analysis/{analysis.json()['id']}",
            headers=headers,
        )
        assert analysis_read.status_code == 200, email
        assert analysis_read.json()["id"] == analysis.json()["id"], email


# ---------------------------------------------------------------------------
# Idempotenz + IDOR
# ---------------------------------------------------------------------------


async def test_second_dissolve_is_a_no_op_without_duplicate_events(client, sessionmaker) -> None:
    workspace_id, connection_id = await _connect(
        client, sessionmaker, "dis-idem-a@example.com", "dis-idem-b@example.com"
    )
    headers_b = await _switch_user(client, "dis-idem-b@example.com")

    first = await _dissolve(client, connection_id, headers_b)
    assert first["status"] == "DISSOLVED"

    async with sessionmaker() as db:
        grants = (
            (
                await db.execute(
                    select(ConsentGrant).where(ConsentGrant.workspace_id == workspace_id)
                )
            )
            .scalars()
            .all()
        )
        revoked_at_after_first = {g.id: g.revoked_at for g in grants}
        events_after_first = (
            await db.execute(
                select(func.count())
                .select_from(ConsentEvent)
                .where(
                    ConsentEvent.grant_id.in_(list(revoked_at_after_first)),
                    ConsentEvent.event_type == "REVOKED",
                )
            )
        ).scalar_one()

    headers_a = await _switch_user(client, "dis-idem-a@example.com")
    second = await _dissolve(client, connection_id, headers_a)
    assert second["status"] == "DISSOLVED"
    assert second["dissolved_at"] == first["dissolved_at"]

    async with sessionmaker() as db:
        grants = (
            (
                await db.execute(
                    select(ConsentGrant).where(ConsentGrant.workspace_id == workspace_id)
                )
            )
            .scalars()
            .all()
        )
        assert {g.id: g.revoked_at for g in grants} == revoked_at_after_first
        events_after_second = (
            await db.execute(
                select(func.count())
                .select_from(ConsentEvent)
                .where(
                    ConsentEvent.grant_id.in_(list(revoked_at_after_first)),
                    ConsentEvent.event_type == "REVOKED",
                )
            )
        ).scalar_one()
        assert events_after_second == events_after_first


async def test_dissolve_idor_third_user_gets_404(client, sessionmaker) -> None:
    """Der Fremde darf weder den Dissolve auslösen noch überhaupt erfahren, dass es die
    Connection gibt -- 404, nie 403/409."""
    _workspace_id, connection_id = await _connect(
        client, sessionmaker, "dis-idor-a@example.com", "dis-idor-b@example.com"
    )
    headers_c = await _signup(client, sessionmaker, "dis-idor-c@example.com")

    response = await client.post(f"/v1/connections/{connection_id}/dissolve", headers=headers_c)
    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
