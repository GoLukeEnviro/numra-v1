"""PR-V2-08 -- Roadmaps (routes/relationship_roadmaps.py,
services/relationship_roadmap_service.py). Reuses the `_connect` two-user helper
pattern from test_workspace_tasks.py / test_checkins.py.
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


async def _create_roadmap(client, workspace_id, headers, title="Reconnect") -> dict:
    response = await client.post(
        f"/v1/workspaces/{workspace_id}/roadmaps",
        json={"roadmap_type": "14_DAY", "title": title},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


# ---------------------------------------------------------------------------
# Roadmap state machine
# ---------------------------------------------------------------------------


async def test_create_roadmap_starts_proposed(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "rm-a@example.com", "rm-b@example.com")
    headers_b = await _switch_user(client, "rm-b@example.com")

    roadmap = await _create_roadmap(client, workspace_id, headers_b)
    assert roadmap["status"] == "PROPOSED"
    assert roadmap["roadmap_type"] == "14_DAY"


async def test_accept_moves_proposed_to_accepted(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "acc-a@example.com", "acc-b@example.com")
    headers_a = await _switch_user(client, "acc-a@example.com")
    roadmap = await _create_roadmap(client, workspace_id, headers_a)

    accept = await client.patch(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}",
        json={"status": "ACCEPTED"},
        headers=headers_a,
    )
    assert accept.status_code == 200
    assert accept.json()["status"] == "ACCEPTED"


async def test_double_accept_is_409(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "dbl-a@example.com", "dbl-b@example.com")
    headers_a = await _switch_user(client, "dbl-a@example.com")
    roadmap = await _create_roadmap(client, workspace_id, headers_a)

    first = await client.patch(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}",
        json={"status": "ACCEPTED"},
        headers=headers_a,
    )
    assert first.status_code == 200
    second = await client.patch(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}",
        json={"status": "ACCEPTED"},
        headers=headers_a,
    )
    assert second.status_code == 409
    assert second.json()["code"] == "ROADMAP_TRANSITION_CONFLICT"


@pytest.mark.parametrize("start_status", ["PROPOSED", "ACCEPTED"])
async def test_archive_from_every_non_terminal_status(client, sessionmaker, start_status) -> None:
    workspace_id = await _connect(
        client,
        sessionmaker,
        f"arch-a-{start_status}@example.com",
        f"arch-b-{start_status}@example.com",
    )
    headers_a = await _switch_user(client, f"arch-a-{start_status}@example.com")
    roadmap = await _create_roadmap(client, workspace_id, headers_a)

    if start_status == "ACCEPTED":
        await client.patch(
            f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}",
            json={"status": "ACCEPTED"},
            headers=headers_a,
        )

    archive = await client.patch(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}",
        json={"status": "ARCHIVED"},
        headers=headers_a,
    )
    assert archive.status_code == 200
    assert archive.json()["status"] == "ARCHIVED"


async def test_delete_only_allowed_for_proposed_or_archived(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "del-a@example.com", "del-b@example.com")
    headers_a = await _switch_user(client, "del-a@example.com")
    roadmap = await _create_roadmap(client, workspace_id, headers_a)

    await client.patch(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}",
        json={"status": "ACCEPTED"},
        headers=headers_a,
    )
    not_deletable = await client.delete(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}", headers=headers_a
    )
    assert not_deletable.status_code == 422
    assert not_deletable.json()["code"] == "ROADMAP_NOT_DELETABLE"

    await client.patch(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}",
        json={"status": "ARCHIVED"},
        headers=headers_a,
    )
    deletable = await client.delete(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}", headers=headers_a
    )
    assert deletable.status_code == 204


async def test_patch_title_rejected_once_archived(client, sessionmaker) -> None:
    workspace_id = await _connect(
        client, sessionmaker, "roarch-a@example.com", "roarch-b@example.com"
    )
    headers_a = await _switch_user(client, "roarch-a@example.com")
    roadmap = await _create_roadmap(client, workspace_id, headers_a)

    await client.patch(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}",
        json={"status": "ARCHIVED"},
        headers=headers_a,
    )
    response = await client.patch(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}",
        json={"title": "Renamed"},
        headers=headers_a,
    )
    assert response.status_code == 422
    assert response.json()["code"] == "ROADMAP_ARCHIVED"


# ---------------------------------------------------------------------------
# Milestone completion + REVIEW_POINT discriminator
# ---------------------------------------------------------------------------


async def test_milestone_completion_only_via_explicit_patch(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "ms-a@example.com", "ms-b@example.com")
    headers_a = await _switch_user(client, "ms-a@example.com")
    roadmap = await _create_roadmap(client, workspace_id, headers_a)

    create = await client.post(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}/milestones",
        json={"milestone_type": "MILESTONE", "title": "Weekly date", "sequence": 1},
        headers=headers_a,
    )
    assert create.status_code == 201
    milestone = create.json()
    assert milestone["status"] == "PENDING"
    assert milestone["completed_at"] is None

    patch = await client.patch(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}/milestones/{milestone['id']}",
        json={"status": "COMPLETED"},
        headers=headers_a,
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == "COMPLETED"
    assert patch.json()["completed_at"] is not None


async def test_review_point_discriminator_filterable(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "rp-a@example.com", "rp-b@example.com")
    headers_a = await _switch_user(client, "rp-a@example.com")
    roadmap = await _create_roadmap(client, workspace_id, headers_a)

    await client.post(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}/milestones",
        json={"milestone_type": "MILESTONE", "title": "Milestone 1", "sequence": 1},
        headers=headers_a,
    )
    await client.post(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}/milestones",
        json={"milestone_type": "REVIEW_POINT", "title": "Check in", "sequence": 2},
        headers=headers_a,
    )

    all_response = await client.get(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}/milestones", headers=headers_a
    )
    assert len(all_response.json()) == 2

    review_only = await client.get(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}/milestones"
        "?milestone_type=REVIEW_POINT",
        headers=headers_a,
    )
    assert len(review_only.json()) == 1
    assert review_only.json()[0]["milestone_type"] == "REVIEW_POINT"


# ---------------------------------------------------------------------------
# Task <-> Milestone link
# ---------------------------------------------------------------------------


async def test_task_milestone_link_same_workspace_succeeds(client, sessionmaker) -> None:
    workspace_id = await _connect(client, sessionmaker, "link-a@example.com", "link-b@example.com")
    headers_a = await _switch_user(client, "link-a@example.com")
    roadmap = await _create_roadmap(client, workspace_id, headers_a)
    milestone = (
        await client.post(
            f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}/milestones",
            json={"milestone_type": "MILESTONE", "title": "M1", "sequence": 1},
            headers=headers_a,
        )
    ).json()

    task = await client.post(
        f"/v1/workspaces/{workspace_id}/tasks",
        json={
            "task_type": "JOINT_SHARED",
            "title": "Linked task",
            "roadmap_milestone_id": milestone["id"],
        },
        headers=headers_a,
    )
    assert task.status_code == 201
    assert task.json()["roadmap_milestone_id"] == milestone["id"]


async def test_task_milestone_link_cross_workspace_is_422(client, sessionmaker) -> None:
    workspace_x = await _connect(client, sessionmaker, "xw-a@example.com", "xw-b@example.com")
    headers_x = await _switch_user(client, "xw-a@example.com")
    roadmap_x = await _create_roadmap(client, workspace_x, headers_x)
    milestone_x = (
        await client.post(
            f"/v1/workspaces/{workspace_x}/roadmaps/{roadmap_x['id']}/milestones",
            json={"milestone_type": "MILESTONE", "title": "In X", "sequence": 1},
            headers=headers_x,
        )
    ).json()

    workspace_y = await _connect(client, sessionmaker, "yw-a@example.com", "yw-b@example.com")
    headers_y = await _switch_user(client, "yw-a@example.com")

    task = await client.post(
        f"/v1/workspaces/{workspace_y}/tasks",
        json={
            "task_type": "JOINT_SHARED",
            "title": "Cross-workspace link attempt",
            "roadmap_milestone_id": milestone_x["id"],
        },
        headers=headers_y,
    )
    assert task.status_code == 422
    assert task.json()["code"] == "MILESTONE_NOT_IN_WORKSPACE"

    local_task = (
        await client.post(
            f"/v1/workspaces/{workspace_y}/tasks",
            json={"task_type": "JOINT_SHARED", "title": "Local task"},
            headers=headers_y,
        )
    ).json()
    patch = await client.patch(
        f"/v1/workspaces/{workspace_y}/tasks/{local_task['id']}",
        json={"roadmap_milestone_id": milestone_x["id"]},
        headers=headers_y,
    )
    assert patch.status_code == 422
    assert patch.json()["code"] == "MILESTONE_NOT_IN_WORKSPACE"


# ---------------------------------------------------------------------------
# IDOR
# ---------------------------------------------------------------------------


async def test_non_member_gets_404_on_all_roadmap_and_milestone_routes(
    client, sessionmaker
) -> None:
    workspace_id = await _connect(client, sessionmaker, "idor-a@example.com", "idor-b@example.com")
    headers_a = await _switch_user(client, "idor-a@example.com")
    roadmap = await _create_roadmap(client, workspace_id, headers_a)
    milestone = (
        await client.post(
            f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}/milestones",
            json={"milestone_type": "MILESTONE", "title": "M1", "sequence": 1},
            headers=headers_a,
        )
    ).json()

    headers_c = await _signup(client, sessionmaker, "idor-c@example.com")

    responses = [
        await client.get(f"/v1/workspaces/{workspace_id}/roadmaps", headers=headers_c),
        await client.get(
            f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}", headers=headers_c
        ),
        await client.patch(
            f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}",
            json={"title": "Hacked"},
            headers=headers_c,
        ),
        await client.delete(
            f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}", headers=headers_c
        ),
        await client.get(
            f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}/milestones", headers=headers_c
        ),
        await client.get(
            f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}/milestones/{milestone['id']}",
            headers=headers_c,
        ),
        await client.patch(
            f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}/milestones/{milestone['id']}",
            json={"title": "Hacked"},
            headers=headers_c,
        ),
        await client.delete(
            f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap['id']}/milestones/{milestone['id']}",
            headers=headers_c,
        ),
    ]
    for response in responses:
        assert response.status_code == 404, response.request.url


# ---------------------------------------------------------------------------
# AVENYTH-suggested -- internal-only, no route exposes it
# ---------------------------------------------------------------------------


async def test_create_avenyth_suggested_roadmap_internal_only_never_auto_accepted(
    client, sessionmaker
) -> None:
    from numra_api.services.relationship_roadmap_service import (
        create_avenyth_suggested_roadmap,
    )

    workspace_id = await _connect(client, sessionmaker, "avi-a@example.com", "avi-b@example.com")
    headers_a = await _switch_user(client, "avi-a@example.com")

    async with sessionmaker() as db:
        roadmap = await create_avenyth_suggested_roadmap(
            db,
            workspace_id=uuid.UUID(workspace_id),
            roadmap_type="14_DAY",
            title="Suggested by the copilot",
            source_analysis_id=uuid.uuid4(),
            prompt_version="v1",
            knowledge_version="v1",
        )
        await db.commit()
        roadmap_id = str(roadmap.id)

    assert roadmap.status.value == "PROPOSED"
    assert roadmap.proposer_user_id is None

    get_roadmap = await client.get(
        f"/v1/workspaces/{workspace_id}/roadmaps/{roadmap_id}", headers=headers_a
    )
    assert get_roadmap.status_code == 200
    assert get_roadmap.json()["status"] == "PROPOSED"
    assert get_roadmap.json()["source_analysis_id"] is not None


async def test_no_route_exposes_create_avenyth_suggested_roadmap(client, sessionmaker) -> None:
    """Introspection test -- create_avenyth_suggested_roadmap must never be
    reachable through any registered FastAPI route (specs/v2/roadmap-spec.md:
    the LLM never marks state transitions; provenance-carrying roadmaps are
    always server-internal-only)."""
    from numra_api.app import app
    from numra_api.services import relationship_roadmap_service

    for route in app.routes:
        endpoint = getattr(route, "endpoint", None)
        if endpoint is None:
            continue
        assert endpoint is not relationship_roadmap_service.create_avenyth_suggested_roadmap


# ---------------------------------------------------------------------------
# Provenance CHECK constraint
# ---------------------------------------------------------------------------


async def test_provenance_fields_on_user_proposed_roadmap_violates_check_constraint(
    sessionmaker,
) -> None:
    from numra_api.models import RelationshipRoadmap, UserConnection
    from numra_api.repositories.workspaces import (
        create_relationship_workspace,
        create_workspace_member,
    )

    async with sessionmaker() as db:
        user_a = await create_user(
            db, email="rmprov-a@example.com", password_hash=hash_password("password12345")
        )
        user_b = await create_user(
            db, email="rmprov-b@example.com", password_hash=hash_password("password12345")
        )
        await db.flush()
        connection = UserConnection(user_a_id=user_a.id, user_b_id=user_b.id)
        db.add(connection)
        await db.flush()
        workspace = await create_relationship_workspace(db, connection_id=connection.id)
        await create_workspace_member(db, workspace_id=workspace.id, user_id=user_a.id)
        await create_workspace_member(db, workspace_id=workspace.id, user_id=user_b.id)

        roadmap = RelationshipRoadmap(
            workspace_id=workspace.id,
            roadmap_type="14_DAY",
            title="Illegal provenance",
            status="PROPOSED",
            proposer_user_id=user_a.id,
            source_analysis_id=uuid.uuid4(),
        )
        db.add(roadmap)
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()
