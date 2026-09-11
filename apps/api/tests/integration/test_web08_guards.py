"""WEB-08 regressions: retained history and explicit task acceptance."""

from __future__ import annotations

import pytest
from test_dissolution import _connect, _dissolve, _signup, _switch_user

pytestmark = pytest.mark.integration


async def test_dissolved_roadmap_history_is_not_deletable(client, sessionmaker):
    ws, connection = await _connect(
        client, sessionmaker, "guard-a@example.com", "guard-b@example.com"
    )
    headers = await _switch_user(client, "guard-a@example.com")
    base = f"/v1/workspaces/{ws}/roadmaps"
    roadmap = (
        await client.post(
            base, headers=headers, json={"title": "History", "roadmap_type": "14_DAY"}
        )
    ).json()
    route = f"{base}/{roadmap['id']}"
    milestone = (
        await client.post(
            f"{route}/milestones",
            headers=headers,
            json={"title": "Step", "milestone_type": "MILESTONE"},
        )
    ).json()
    await _dissolve(client, connection, headers)
    for email in ["guard-a@example.com", "guard-b@example.com"]:
        headers = await _switch_user(client, email)
        for path in [route, f"{route}/milestones/{milestone['id']}"]:
            assert (await client.delete(path, headers=headers)).status_code == 409
            assert (await client.get(path, headers=headers)).status_code == 200
    headers = await _signup(client, sessionmaker, "guard-c@example.com")
    assert (await client.delete(route, headers=headers)).status_code == 404


async def test_archived_roadmap_children_are_readonly(client, sessionmaker):
    ws, _ = await _connect(client, sessionmaker, "archive-a@example.com", "archive-b@example.com")
    headers = await _switch_user(client, "archive-a@example.com")
    base = f"/v1/workspaces/{ws}/roadmaps"
    roadmap = (
        await client.post(
            base, headers=headers, json={"title": "History", "roadmap_type": "QUARTER"}
        )
    ).json()
    route = f"{base}/{roadmap['id']}"
    milestone = (
        await client.post(
            f"{route}/milestones",
            headers=headers,
            json={"title": "Step", "milestone_type": "REVIEW_POINT"},
        )
    ).json()
    linked_task = (
        await client.post(
            f"/v1/workspaces/{ws}/tasks",
            headers=headers,
            json={
                "title": "Linked work",
                "task_type": "JOINT_SHARED",
                "roadmap_milestone_id": milestone["id"],
            },
        )
    ).json()
    assert (
        await client.patch(route, headers=headers, json={"status": "ARCHIVED"})
    ).status_code == 200
    assert (
        await client.post(
            f"{route}/milestones",
            headers=headers,
            json={"title": "Extra", "milestone_type": "MILESTONE", "sequence": 1},
        )
    ).status_code == 422
    path = f"{route}/milestones/{milestone['id']}"
    assert (
        await client.patch(path, headers=headers, json={"status": "COMPLETED"})
    ).status_code == 422
    assert (await client.delete(path, headers=headers)).status_code == 422
    assert (await client.get(path, headers=headers)).json()["status"] == "PENDING"
    assert (
        await client.patch(
            f"/v1/workspaces/{ws}/tasks/{linked_task['id']}",
            headers=headers,
            json={"roadmap_milestone_id": None},
        )
    ).status_code == 422
    assert (
        await client.post(
            f"/v1/workspaces/{ws}/tasks",
            headers=headers,
            json={
                "title": "Late link",
                "task_type": "JOINT_SHARED",
                "roadmap_milestone_id": milestone["id"],
            },
        )
    ).status_code == 422


async def test_partner_task_requires_acceptance_before_completion(client, sessionmaker):
    ws, _ = await _connect(
        client, sessionmaker, "taskguard-a@example.com", "taskguard-b@example.com"
    )
    headers = await _switch_user(client, "taskguard-a@example.com")
    base = f"/v1/workspaces/{ws}/tasks"
    task = (
        await client.post(
            base, headers=headers, json={"title": "Proposal", "task_type": "FOR_PARTNER_PROPOSED"}
        )
    ).json()
    route = f"{base}/{task['id']}"
    for email in ["taskguard-a@example.com", "taskguard-b@example.com"]:
        headers = await _switch_user(client, email)
        assert (
            await client.patch(route, headers=headers, json={"status": "COMPLETED"})
        ).status_code == 409
    assert (await client.post(f"{route}/accept", headers=headers)).status_code == 200
    assert (
        await client.patch(route, headers=headers, json={"status": "COMPLETED"})
    ).status_code == 200
    assert (
        await client.patch(route, headers=headers, json={"status": "COMPLETED"})
    ).status_code == 409


async def test_dissolved_shared_copy_cannot_be_deleted(client, sessionmaker, lukas_payload):
    ws, connection = await _connect(
        client, sessionmaker, "copy-a@example.com", "copy-b@example.com"
    )
    headers = await _switch_user(client, "copy-a@example.com")
    person = (await client.post("/v1/people", headers=headers, json=lukas_payload)).json()
    reflection = (
        await client.post(
            f"/v1/people/{person['id']}/private-reflections",
            headers=headers,
            json={"entry_date": "2026-09-11", "content": "Synthetic private note"},
        )
    ).json()
    copy = (
        await client.post(
            f"/v1/private-reflections/{reflection['id']}/share",
            headers=headers,
            json={"workspace_id": ws},
        )
    ).json()
    await _dissolve(client, connection, headers)
    route = f"/v1/workspaces/{ws}/shared-reflections/{copy['id']}"
    assert (await client.delete(route, headers=headers)).status_code == 409
    assert (await client.get(route, headers=headers)).json()["content"] == "Synthetic private note"
    headers = await _switch_user(client, "copy-b@example.com")
    assert (await client.delete(route, headers=headers)).status_code == 404
