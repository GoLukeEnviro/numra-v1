"""PR-V2-07 -- Shared Task System (routes/workspace_tasks.py,
services/workspace_task_service.py). Reuses the `_connect` two-user helper
pattern from test_checkins.py / test_consent_idor.py.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from numra_api.auth.passwords import hash_password
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


async def _connect(client, sessionmaker, email_a: str, email_b: str) -> str:
    """Leaves the active session as user B (the redeemer)."""
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
    return redeem.json()["workspace_id"]


# ---------------------------------------------------------------------------
# Proposal flow (FOR_PARTNER_PROPOSED)
# ---------------------------------------------------------------------------


async def test_for_partner_proposed_derives_recipient_from_membership(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "prop-a@example.com", "prop-b@example.com")
    headers_a = await _switch_user(client, "prop-a@example.com")

    create = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={"task_type": "FOR_PARTNER_PROPOSED", "title": "Plan date night"},
        headers=headers_a,
    )
    assert create.status_code == 201
    body = create.json()
    assert body["status"] == "PROPOSED"
    assert body["task_type"] == "FOR_PARTNER_PROPOSED"

    headers_b = await _switch_user(client, "prop-b@example.com")
    me = await client.get("/v1/auth/me", headers=headers_b)
    assert body["recipient_user_id"] == me.json()["id"]


async def test_body_recipient_mismatch_is_422(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "spoof-a@example.com", "spoof-b@example.com"
    )
    headers_a = await _switch_user(client, "spoof-a@example.com")

    create = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={
            "task_type": "FOR_PARTNER_PROPOSED",
            "title": "Spoofed",
            "recipient_user_id": str(uuid.uuid4()),
        },
        headers=headers_a,
    )
    assert create.status_code == 422
    assert create.json()["code"] == "INVALID_RECIPIENT"


# ---------------------------------------------------------------------------
# Accept/decline state machine
# ---------------------------------------------------------------------------


async def test_accept_moves_proposed_directly_to_active(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "acc-a@example.com", "acc-b@example.com")
    headers_a = await _switch_user(client, "acc-a@example.com")
    create = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={"task_type": "FOR_PARTNER_PROPOSED", "title": "Cook dinner"},
        headers=headers_a,
    )
    task_id = create.json()["id"]

    headers_b = await _switch_user(client, "acc-b@example.com")
    accept = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks/{task_id}/accept", headers=headers_b
    )
    assert accept.status_code == 200
    assert accept.json()["status"] == "ACTIVE"


async def test_decline_moves_proposed_to_declined(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "dec-a@example.com", "dec-b@example.com")
    headers_a = await _switch_user(client, "dec-a@example.com")
    create = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={"task_type": "FOR_PARTNER_PROPOSED", "title": "Wash car"},
        headers=headers_a,
    )
    task_id = create.json()["id"]

    headers_b = await _switch_user(client, "dec-b@example.com")
    decline = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks/{task_id}/decline", headers=headers_b
    )
    assert decline.status_code == 200
    assert decline.json()["status"] == "DECLINED"


async def test_double_accept_is_409(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "dbla-a@example.com", "dbla-b@example.com")
    headers_a = await _switch_user(client, "dbla-a@example.com")
    create = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={"task_type": "FOR_PARTNER_PROPOSED", "title": "Repeat"},
        headers=headers_a,
    )
    task_id = create.json()["id"]

    headers_b = await _switch_user(client, "dbla-b@example.com")
    first = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks/{task_id}/accept", headers=headers_b
    )
    assert first.status_code == 200
    second = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks/{task_id}/accept", headers=headers_b
    )
    assert second.status_code == 409
    assert second.json()["code"] == "TASK_TRANSITION_CONFLICT"


async def test_double_decline_is_409(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "dbld-a@example.com", "dbld-b@example.com")
    headers_a = await _switch_user(client, "dbld-a@example.com")
    create = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={"task_type": "FOR_PARTNER_PROPOSED", "title": "Repeat decline"},
        headers=headers_a,
    )
    task_id = create.json()["id"]

    headers_b = await _switch_user(client, "dbld-b@example.com")
    first = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks/{task_id}/decline", headers=headers_b
    )
    assert first.status_code == 200
    second = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks/{task_id}/decline", headers=headers_b
    )
    assert second.status_code == 409
    assert second.json()["code"] == "TASK_TRANSITION_CONFLICT"


async def test_self_accept_by_proposer_is_404(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "self-a@example.com", "self-b@example.com")
    headers_a = await _switch_user(client, "self-a@example.com")
    create = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={"task_type": "FOR_PARTNER_PROPOSED", "title": "Self accept"},
        headers=headers_a,
    )
    task_id = create.json()["id"]

    accept = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks/{task_id}/accept", headers=headers_a
    )
    assert accept.status_code == 404


# ---------------------------------------------------------------------------
# IDOR
# ---------------------------------------------------------------------------


async def test_non_member_gets_404_on_get_accept_decline_patch(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "idor-a@example.com", "idor-b@example.com")
    headers_a = await _switch_user(client, "idor-a@example.com")
    create = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={"task_type": "JOINT_SHARED", "title": "Joint chore"},
        headers=headers_a,
    )
    task_id = create.json()["id"]

    headers_c = await _signup(client, sessionmaker, "idor-c@example.com")

    responses = [
        await client.get(f"/v1/workspaces/{workspace_id}/tasks/{task_id}", headers=headers_c),
        await client.get(f"/v1/workspaces/{workspace_id}/tasks", headers=headers_c),
        await client.post(
            f"/v1/workspaces/{workspace_id}/tasks/{task_id}/accept", headers=headers_c
        ),
        await client.post(
            f"/v1/workspaces/{workspace_id}/tasks/{task_id}/decline", headers=headers_c
        ),
        await client.patch(
            f"/v1/workspaces/{workspace_id}/tasks/{task_id}",
            json={"title": "Hacked"},
            headers=headers_c,
        ),
        await client.delete(f"/v1/workspaces/{workspace_id}/tasks/{task_id}", headers=headers_c),
    ]
    for response in responses:
        assert response.status_code == 404, response.request.url


async def test_cross_workspace_idor_task_from_other_workspace_is_404(client, sessionmaker) -> None:
    workspace_x = await _connect(client, sessionmaker, "xw-a@example.com", "xw-b@example.com")
    headers_a = await _switch_user(client, "xw-a@example.com")
    create = await client.post(
        f"/v1/workspaces/{workspace_x}/tasks",
        json={"task_type": "JOINT_SHARED", "title": "In workspace X"},
        headers=headers_a,
    )
    task_id = create.json()["id"]

    workspace_y = await _connect(client, sessionmaker, "yw-c@example.com", "yw-d@example.com")
    headers_c = await _switch_user(client, "yw-c@example.com")

    response = await client.get(f"/v1/workspaces/{workspace_y}/tasks/{task_id}", headers=headers_c)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# JOINT_SHARED immediate activation
# ---------------------------------------------------------------------------


async def test_joint_shared_active_immediately_no_accept(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "joint-a@example.com", "joint-b@example.com"
    )
    headers_a = await _switch_user(client, "joint-a@example.com")

    create = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={"task_type": "JOINT_SHARED", "title": "Plan trip"},
        headers=headers_a,
    )
    assert create.status_code == 201
    assert create.json()["status"] == "ACTIVE"

    # Visible to the non-proposing member too, without any accept step.
    headers_b = await _switch_user(client, "joint-b@example.com")
    task_id = create.json()["id"]
    get_b = await client.get(f"/v1/workspaces/{workspace_id}/tasks/{task_id}", headers=headers_b)
    assert get_b.status_code == 200
    assert get_b.json()["status"] == "ACTIVE"


# ---------------------------------------------------------------------------
# AVENYTH_SUGGESTED -- never user-creatable via the route, never auto-active
# ---------------------------------------------------------------------------


async def test_avenyth_suggested_not_creatable_via_route(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "av-a@example.com", "av-b@example.com")
    headers_a = await _switch_user(client, "av-a@example.com")

    create = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={"task_type": "AVENYTH_SUGGESTED", "title": "Should never work"},
        headers=headers_a,
    )
    assert create.status_code == 422
    assert create.json()["code"] == "AVENYTH_SUGGESTED_NOT_USER_CREATABLE"


async def test_avenyth_suggestion_internal_service_never_auto_active(client, sessionmaker) -> None:
    from numra_api.services.workspace_task_service import create_avenyth_suggestion

    workspace_id = await _connect(client, sessionmaker, "avi-a@example.com", "avi-b@example.com")
    headers_a = await _switch_user(client, "avi-a@example.com")

    async with sessionmaker() as db:
        task = await create_avenyth_suggestion(
            db,
            workspace_id=uuid.UUID(workspace_id),
            title="Suggested by the copilot",
            description=None,
            due_date=None,
            source_analysis_id=uuid.uuid4(),
            prompt_version="v1",
            knowledge_version="v1",
        )
        await db.commit()
        task_id = str(task.id)

    assert task.status.value == "PROPOSED"
    assert task.proposer_user_id is None

    get_task = await client.get(f"/v1/workspaces/{workspace_id}/tasks/{task_id}", headers=headers_a)
    assert get_task.status_code == 200
    assert get_task.json()["status"] == "PROPOSED"
    assert get_task.json()["source_analysis_id"] is not None
    assert get_task.json()["prompt_version"] == "v1"

    # Accepting an AVENYTH_SUGGESTED task requires an explicit member action --
    # any ACTIVE member may do it, since there is no fixed recipient.
    accept = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks/{task_id}/accept", headers=headers_a
    )
    assert accept.status_code == 200
    assert accept.json()["status"] == "ACTIVE"


# ---------------------------------------------------------------------------
# Provenance CHECK constraint
# ---------------------------------------------------------------------------


async def test_provenance_fields_on_non_avenyth_type_violates_check_constraint(
    sessionmaker,
) -> None:
    from numra_api.models import UserConnection, WorkspaceTask
    from numra_api.models.enums import TaskType, WorkspaceTaskStatus
    from numra_api.repositories.users import create_user
    from numra_api.repositories.workspaces import (
        create_relationship_workspace,
        create_workspace_member,
    )

    async with sessionmaker() as db:
        user_a = await create_user(
            db, email="prov-a@example.com", password_hash=hash_password("password12345")
        )
        user_b = await create_user(
            db, email="prov-b@example.com", password_hash=hash_password("password12345")
        )
        await db.flush()
        connection = UserConnection(user_a_id=user_a.id, user_b_id=user_b.id)
        db.add(connection)
        await db.flush()
        workspace = await create_relationship_workspace(db, connection_id=connection.id)
        await create_workspace_member(db, workspace_id=workspace.id, user_id=user_a.id)
        await create_workspace_member(db, workspace_id=workspace.id, user_id=user_b.id)

        task = WorkspaceTask(
            workspace_id=workspace.id,
            task_type=TaskType.JOINT_SHARED,
            status=WorkspaceTaskStatus.ACTIVE,
            proposer_user_id=user_a.id,
            recipient_user_id=None,
            title="Illegal provenance",
            source_analysis_id=uuid.uuid4(),
        )
        db.add(task)
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()
