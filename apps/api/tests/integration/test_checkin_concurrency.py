"""Real PostgreSQL transactions. Every race proves a blocked backend PID before commit.

The first operation has finished its writes but its transaction/lock is still open.
The second runs on another connection. An observer verifies pg_blocking_pids before
releasing the first. No barrier inside mutually dependent locks; bounded cleanup.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import func, select, text
from test_checkins import _connect

from numra_api.models import CheckinAnalysis, CheckinResponse, CheckinTemplate, User
from numra_api.services import checkin_service as svc
from numra_api.services.connection_service import dissolve_own_connection
from numra_api.services.errors import ApplicationError
from numra_api.services.relationship_workspace_service import patch_relationship_type


async def _overlap(sessionmaker, first, second):
    async with sessionmaker() as left:
        left_pid = await left.scalar(text("SELECT pg_backend_pid()"))
        first_result = await first(left)
        ready = asyncio.Event()
        right_pid = None

        async def contender():
            nonlocal right_pid
            async with sessionmaker() as right:
                right_pid = await right.scalar(text("SELECT pg_backend_pid()"))
                ready.set()
                try:
                    result = await second(right)
                    await right.commit()
                    return result
                except ApplicationError as error:
                    await right.rollback()
                    return error.code

        task = asyncio.create_task(contender())
        try:
            await asyncio.wait_for(ready.wait(), timeout=5)
            assert left_pid != right_pid
            async with sessionmaker() as observer:
                async with asyncio.timeout(5):
                    while True:
                        blockers = await observer.scalar(
                            text("SELECT pg_blocking_pids(:pid)"), {"pid": right_pid}
                        )
                        if left_pid in blockers:
                            break
                        if task.done():
                            pytest.fail(f"contender finished without overlapping: {task.result()}")
                        await asyncio.sleep(0.01)
            await left.commit()
            return first_result, await asyncio.wait_for(task, timeout=10)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


async def _identities(client, sessionmaker):
    wid = uuid.UUID(
        await _connect(client, sessionmaker, "race-a@example.com", "race-b@example.com")
    )
    async with sessionmaker() as db:
        users = list((await db.scalars(select(User.id).order_by(User.email))).all())
    return wid, users[0], users[1]


def _start(wid, uid, key):
    async def run(db):
        return await svc.start_checkin_round(db, workspace_id=wid, user_id=uid, idempotency_key=key)

    return run


def _submit(wid, uid, result, key, value):
    async def run(db):
        return await svc.submit_checkin(
            db,
            workspace_id=wid,
            user_id=uid,
            round_id=result.checkin.id,
            idempotency_key=key,
            responses=[(d.dimension_id, value) for d in result.dimensions],
        )

    return run


def _config(wid, uid, key):
    async def run(db):
        return await svc.create_custom_dimension(
            db,
            workspace_id=wid,
            user_id=uid,
            semantic_key=key,
            label=key,
            description=None,
            scale_min=1,
            scale_max=10,
            sort_order=9,
        )

    return run


@pytest.mark.parametrize("same_key", [True, False])
async def test_start_against_start(client, sessionmaker, same_key):
    wid, a, _ = await _identities(client, sessionmaker)
    first, second = await _overlap(
        sessionmaker, _start(wid, a, "start"), _start(wid, a, "start" if same_key else "other")
    )
    if same_key:
        assert first.checkin.id == second.checkin.id
    else:
        assert second == "CHECKIN_ROUND_OPEN"
    async with sessionmaker() as db:
        rounds = await svc.list_checkins(db, workspace_id=wid, user_id=a, limit=10, offset=0)
        assert len(rounds) == 1


@pytest.mark.parametrize("config_first", [True, False])
async def test_start_against_config(client, sessionmaker, config_first):
    wid, a, b = await _identities(client, sessionmaker)
    start, config = _start(wid, a, "start"), _config(wid, b, "trust")
    first, second = await _overlap(
        sessionmaker, config if config_first else start, start if config_first else config
    )
    if config_first:
        assert len(second.dimensions) == 6
    else:
        assert len(first.dimensions) == 5
        assert second == "CHECKIN_ROUND_OPEN"


async def test_parallel_submits_twenty_rounds(client, sessionmaker):
    wid, a, b = await _identities(client, sessionmaker)
    for attempt in range(20):
        async with sessionmaker() as db:
            result = await _start(wid, a, f"start-{attempt}")(db)
            await db.commit()
        first, second = await _overlap(
            sessionmaker,
            _submit(wid, a, result, f"a-{attempt}", 8),
            _submit(wid, b, result, f"b-{attempt}", 3),
        )
        assert first.checkin.status == "AWAITING_SUBMISSIONS"
        assert second.checkin.status == "ANALYZED"
        assert len(second.my_responses) == 5
        assert second.analysis.result_json["closeness"]["sample_size"] == attempt + 1
        assert second.analysis.result_json["closeness"]["absolute_gap"] == 5
    async with sessionmaker() as db:
        assert await db.scalar(select(func.count()).select_from(CheckinAnalysis)) == 20
        assert await db.scalar(select(func.count()).select_from(CheckinResponse)) == 200
        assert await svc.checkins_repo.get_awaiting_checkin(db, workspace_id=wid) is None


@pytest.mark.parametrize("key_case", ["same", "different", "changed_payload"])
async def test_parallel_duplicate_submits(client, sessionmaker, key_case):
    wid, a, _ = await _identities(client, sessionmaker)
    async with sessionmaker() as db:
        result = await _start(wid, a, "start")(db)
        await db.commit()
    _, second = await _overlap(
        sessionmaker,
        _submit(wid, a, result, "submit", 8),
        _submit(
            wid,
            a,
            result,
            "other" if key_case == "different" else "submit",
            2 if key_case == "changed_payload" else 8,
        ),
    )
    if key_case == "same":
        assert second.checkin.id == result.checkin.id
    else:
        assert second == (
            "CHECKIN_ALREADY_SUBMITTED"
            if key_case == "different"
            else "CHECKIN_IDEMPOTENCY_CONFLICT"
        )
    async with sessionmaker() as db:
        assert await db.scalar(select(func.count()).select_from(CheckinResponse)) == 5
        assert await db.scalar(select(func.count()).select_from(CheckinAnalysis)) == 0


@pytest.mark.parametrize("operation", ["start", "submit", "config", "type"])
@pytest.mark.parametrize("dissolve_first", [True, False])
async def test_mutation_against_dissolve(client, sessionmaker, operation, dissolve_first):
    wid, a, b = await _identities(client, sessionmaker)
    async with sessionmaker() as db:
        workspace = await svc.require_locked_workspace(db, workspace_id=wid, user_id=a)
        connection_id = workspace.connection_id
        if operation == "submit":
            result = await _start(wid, a, "start")(db)
        await db.commit()

    async def dissolve(db):
        return await dissolve_own_connection(db, connection_id=connection_id, user_id=b)

    async def change_type(db):
        return await patch_relationship_type(
            db, workspace_id=wid, user_id=a, relationship_type="WORK"
        )

    mutation = {
        "start": _start(wid, a, "start"),
        "config": _config(wid, a, "trust"),
        "type": change_type,
    }.get(operation)
    if operation == "submit":
        mutation = _submit(wid, a, result, "submit", 8)
    _, second = await _overlap(
        sessionmaker,
        dissolve if dissolve_first else mutation,
        mutation if dissolve_first else dissolve,
    )
    if dissolve_first:
        assert second == "WORKSPACE_DISSOLVED"
    else:
        assert second.status == "DISSOLVED"
    async with sessionmaker() as db:
        rows = await svc.list_checkins(db, workspace_id=wid, user_id=a, limit=10, offset=0)
        expected = (
            1 if operation == "submit" or (operation == "start" and not dissolve_first) else 0
        )
        assert len(rows) == expected
        count = await db.scalar(select(func.count()).select_from(CheckinResponse))
        assert count == (5 if operation == "submit" and not dissolve_first else 0)


async def test_parallel_config_versions_preserve_both_changes(client, sessionmaker):
    wid, a, b = await _identities(client, sessionmaker)
    async with sessionmaker() as db:
        result = await _start(wid, a, "start")(db)
        await _submit(wid, a, result, "a", 8)(db)
        await _submit(wid, b, result, "b", 3)(db)
        await db.commit()
    await _overlap(sessionmaker, _config(wid, a, "trust"), _config(wid, b, "support"))
    async with sessionmaker() as db:
        template, dims = await svc.get_checkin_template(db, workspace_id=wid, user_id=a)
        assert template.version == 2
        assert {d.semantic_key for d in dims} >= {"trust", "support"}
        assert await db.scalar(select(func.count()).select_from(CheckinTemplate)) == 2
        old, old_dims = await svc.get_checkin_template(db, workspace_id=wid, user_id=a, version=1)
        assert not old.active and len(old_dims) == 5


@pytest.mark.parametrize("type_first", [True, False])
async def test_start_against_relationship_type(client, sessionmaker, type_first):
    wid, a, b = await _identities(client, sessionmaker)

    async def change_type(db):
        return await patch_relationship_type(
            db, workspace_id=wid, user_id=b, relationship_type="WORK"
        )

    start = _start(wid, a, "start")
    _, second = await _overlap(
        sessionmaker, change_type if type_first else start, start if type_first else change_type
    )
    if type_first:
        assert second.checkin.status == "AWAITING_SUBMISSIONS"
    else:
        assert second == "CHECKIN_ROUND_OPEN"


async def test_current_waits_for_committed_analysis(client, sessionmaker):
    wid, a, b = await _identities(client, sessionmaker)
    async with sessionmaker() as db:
        result = await _start(wid, a, "start")(db)
        await _submit(wid, a, result, "a", 8)(db)
        await db.commit()

    async def current(db):
        return await svc.get_current_checkin(db, workspace_id=wid, user_id=a)

    _, observed = await _overlap(sessionmaker, _submit(wid, b, result, "b", 3), current)
    assert observed.checkin.status == "ANALYZED"
    assert observed.analysis is not None
    assert observed.partner_submitted is True


async def test_membership_revoked_while_waiting_rechecked(client, sessionmaker):
    from sqlalchemy import update

    from numra_api.models import WorkspaceMember
    from numra_api.models.enums import WorkspaceMemberStatus

    wid, a, _ = await _identities(client, sessionmaker)

    async def remove_member(db):
        await svc.require_locked_workspace(db, workspace_id=wid, user_id=a)
        await db.execute(
            update(WorkspaceMember)
            .where(WorkspaceMember.user_id == a)
            .values(status=WorkspaceMemberStatus.REMOVED)
        )

    _, response = await _overlap(sessionmaker, remove_member, _start(wid, a, "blocked"))
    assert response == "NOT_FOUND"
