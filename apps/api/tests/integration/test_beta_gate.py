"""D4: closed-beta gate (flag AND individual grant), admin grant/revoke + audit,
worker start check, transition inventory/backfill."""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from numra_api.auth.passwords import hash_password
from numra_api.models import AdminAuditEvent, ReportJob
from numra_api.models.enums import ReportJobStatus, UserRole
from numra_api.repositories.entitlements import grant_beta_access
from numra_api.repositories.users import create_user, set_user_role
from numra_api.services.beta_inventory import backfill_beta_access, collect_usage
from numra_api.worker import run_one_cycle

pytestmark = pytest.mark.integration

PASSWORD = "correct horse battery staple"
RANDOM = "00000000-0000-4000-8000-000000000001"


@pytest.fixture
def enforce_gate(app, settings):
    app.state.settings = settings.model_copy(update={"beta_gate_enforced": True})


async def _user(sessionmaker, email: str, *, role: UserRole = UserRole.USER, granted: bool = False):
    async with sessionmaker() as db:
        user = await create_user(db, email=email, password_hash=hash_password(PASSWORD))
        if role != UserRole.USER:
            await set_user_role(db, user=user, role=role)
        if granted:
            await grant_beta_access(db, user_id=user.id)
        await db.commit()
        return user


async def _login(client, email: str) -> dict[str, str]:
    response = await client.post("/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _first_report(client, headers, payload):
    person = (await client.post("/v1/people", json=payload, headers=headers)).json()
    calc = (
        await client.post(
            f"/v1/people/{person['id']}/calculations",
            json={"as_of_date": "2026-01-01"},
            headers=headers,
        )
    ).json()
    return await client.post(
        "/v1/reports", json={"calculation_id": calc["id"], "report_type": "QUICK"}, headers=headers
    )


def _entry_points() -> list[tuple[str, dict]]:
    return [
        ("/v1/reports", {"calculation_id": RANDOM, "report_type": "QUICK"}),
        (f"/v1/workspaces/{RANDOM}/relationship-analysis", {}),
        (f"/v1/workspaces/{RANDOM}/shadow-dynamics", {}),
        (f"/v1/workspaces/{RANDOM}/copilot/threads/{RANDOM}/messages", {"content": "hallo"}),
        (f"/v1/me/copilot/threads/{RANDOM}/messages", {"content": "hallo"}),
    ]


async def test_gate_off_by_default_does_not_block(client, sessionmaker, lukas_payload) -> None:
    await _user(sessionmaker, "gate-off@example.com")
    headers = await _login(client, "gate-off@example.com")
    assert (await _first_report(client, headers, lukas_payload)).status_code == 201
    for path, body in _entry_points():
        response = await client.post(path, json=body, headers=headers)
        assert response.status_code != 403 or response.json()["code"] != "BETA_ACCESS_REQUIRED"


async def test_new_account_is_denied_on_every_entry_point(
    client, sessionmaker, enforce_gate
) -> None:
    await _user(sessionmaker, "gate-new@example.com")
    headers = await _login(client, "gate-new@example.com")
    for path, body in _entry_points():
        response = await client.post(path, json=body, headers=headers)
        assert response.status_code == 403, path
        assert response.json()["code"] == "BETA_ACCESS_REQUIRED", path


async def test_grant_opens_and_revoke_closes(
    client, sessionmaker, enforce_gate, lukas_payload
) -> None:
    user = await _user(sessionmaker, "gate-grant@example.com", granted=True)
    headers = await _login(client, "gate-grant@example.com")
    assert (await _first_report(client, headers, lukas_payload)).status_code == 201
    for path, body in _entry_points()[1:]:
        response = await client.post(path, json=body, headers=headers)
        assert response.json().get("code") != "BETA_ACCESS_REQUIRED", path

    from numra_api.repositories.entitlements import revoke_beta_access

    async with sessionmaker() as db:
        assert await revoke_beta_access(db, user_id=user.id) is True
        await db.commit()
    response = await client.post(
        "/v1/reports", json={"calculation_id": RANDOM, "report_type": "QUICK"}, headers=headers
    )
    assert response.status_code == 403


async def test_flag_off_still_wins_over_grant(client, sessionmaker, enforce_gate, app) -> None:
    await _user(sessionmaker, "gate-flag@example.com", granted=True)
    headers = await _login(client, "gate-flag@example.com")
    from numra_api.models import FeatureFlag

    async with sessionmaker() as db:
        flag = (
            await db.execute(select(FeatureFlag).where(FeatureFlag.name == "copilot"))
        ).scalar_one()
        flag.enabled = False
        await db.commit()
    app.state.feature_flag_cache.invalidate()
    response = await client.post(
        f"/v1/me/copilot/threads/{RANDOM}/messages", json={"content": "x"}, headers=headers
    )
    assert response.status_code != 201
    assert response.json()["code"] != "BETA_ACCESS_REQUIRED"


async def test_age_confirmation_and_beta_grant_are_independent(
    client, sessionmaker, enforce_gate
) -> None:
    now = dt.datetime.now(dt.UTC)
    async with sessionmaker() as db:
        aged = await create_user(
            db,
            email="aged@example.com",
            password_hash=hash_password(PASSWORD),
            age_confirmed_at=now,
        )
        unaged = await create_user(
            db, email="unaged@example.com", password_hash=hash_password(PASSWORD)
        )
        await grant_beta_access(db, user_id=unaged.id)
        await db.commit()
        assert aged.age_confirmed_at is not None and unaged.age_confirmed_at is None

    body = {"calculation_id": RANDOM, "report_type": "QUICK"}
    headers = await _login(client, "aged@example.com")
    assert (await client.post("/v1/reports", json=body, headers=headers)).status_code == 403
    headers = await _login(client, "unaged@example.com")
    assert (await client.post("/v1/reports", json=body, headers=headers)).status_code != 403


async def test_admin_grant_revoke_idempotent_with_audit(client, sessionmaker) -> None:
    await _user(sessionmaker, "beta-admin@example.com", role=UserRole.ADMIN)
    target = await _user(sessionmaker, "beta-target@example.com")
    headers = await _login(client, "beta-admin@example.com")
    url = f"/v1/admin/users/{target.id}/beta-access"

    assert (await client.get(url)).json()["granted"] is False
    first = await client.put(url, headers=headers)
    again = await client.put(url, headers=headers)
    assert first.json() == {"user_id": str(target.id), "granted": True, "changed": True}
    assert again.json() == {"user_id": str(target.id), "granted": True, "changed": False}
    assert (await client.get(f"/v1/admin/users/{target.id}")).json()["beta_access"] is True

    gone = await client.delete(url, headers=headers)
    gone_again = await client.delete(url, headers=headers)
    assert gone.json()["changed"] is True and gone_again.json()["changed"] is False

    async with sessionmaker() as db:
        events = (
            (
                await db.execute(
                    select(AdminAuditEvent)
                    .where(AdminAuditEvent.target_user_id == target.id)
                    .order_by(AdminAuditEvent.created_at)
                )
            )
            .scalars()
            .all()
        )
    assert [e.action for e in events] == ["BETA_ACCESS_GRANTED", "BETA_ACCESS_REVOKED"]
    for event in events:
        assert event.actor_user_id is not None
        assert event.safe_metadata == {"entitlement_set": "beta_default", "source": "admin_api"}
        assert "example.com" not in str(event.safe_metadata)


async def test_admin_beta_endpoints_guard_auth_csrf_and_unknown_user(client, sessionmaker) -> None:
    target = await _user(sessionmaker, "beta-guard@example.com")
    url = f"/v1/admin/users/{target.id}/beta-access"
    assert (await client.put(url)).status_code == 401

    await _user(sessionmaker, "beta-plain@example.com")
    headers = await _login(client, "beta-plain@example.com")
    assert (await client.put(url, headers=headers)).status_code == 403

    await _user(sessionmaker, "beta-admin2@example.com", role=UserRole.ADMIN)
    headers = await _login(client, "beta-admin2@example.com")
    assert (await client.put(url)).status_code == 403  # no CSRF header
    assert (
        await client.put(f"/v1/admin/users/{RANDOM}/beta-access", headers=headers)
    ).status_code == 404


async def test_concurrent_grants_create_one_assignment_and_one_audit_event(
    client, sessionmaker, app
) -> None:
    import asyncio

    await _user(sessionmaker, "beta-race-admin@example.com", role=UserRole.ADMIN)
    target = await _user(sessionmaker, "beta-race@example.com")
    headers = await _login(client, "beta-race-admin@example.com")
    cookies = dict(client.cookies)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver", cookies=cookies
    ) as other:
        responses = await asyncio.gather(
            *[
                other.put(f"/v1/admin/users/{target.id}/beta-access", headers=headers)
                for _ in range(8)
            ]
        )
    assert sorted(r.json()["changed"] for r in responses).count(True) == 1
    async with sessionmaker() as db:
        count = len(
            (
                await db.execute(
                    select(AdminAuditEvent).where(AdminAuditEvent.target_user_id == target.id)
                )
            )
            .scalars()
            .all()
        )
    assert count == 1


async def test_entitlements_reflect_gate(client, sessionmaker, enforce_gate) -> None:
    await _user(sessionmaker, "ent-none@example.com")
    await _login(client, "ent-none@example.com")
    body = (await client.get("/v1/me/entitlements")).json()
    assert body["beta_gate_enforced"] is True and body["beta_access"] is False
    assert not (body["premium_reports"] or body["relationship_copilot"])
    assert not body["advanced_relationship_analysis"]
    assert body["connections"] is True

    await _user(sessionmaker, "ent-yes@example.com", granted=True)
    await _login(client, "ent-yes@example.com")
    body = (await client.get("/v1/me/entitlements")).json()
    assert body["beta_access"] is True and body["premium_reports"] is True


async def test_worker_fails_queued_job_of_user_without_grant(
    client, sessionmaker, lukas_payload, llm
) -> None:
    await _user(sessionmaker, "worker-gate@example.com")
    headers = await _login(client, "worker-gate@example.com")
    report = (await _first_report(client, headers, lukas_payload)).json()

    assert await run_one_cycle(sessionmaker, llm=llm, beta_gate_enforced=True) is True

    async with sessionmaker() as db:
        job = (
            await db.execute(select(ReportJob).where(ReportJob.id == uuid.UUID(report["job_id"])))
        ).scalar_one()
    assert job.status == ReportJobStatus.FAILED
    assert job.error_code == "BETA_ACCESS_REQUIRED"


async def test_backfill_is_dry_run_first_then_idempotent(
    client, sessionmaker, lukas_payload
) -> None:
    await _user(sessionmaker, "bf-used@example.com")
    await _user(sessionmaker, "bf-unused@example.com")
    headers = await _login(client, "bf-used@example.com")
    assert (await _first_report(client, headers, lukas_payload)).status_code == 201

    async with sessionmaker() as db:
        rows = await collect_usage(db, secret="s3cret")
        assert len(rows) == 1 and rows[0].reports == 1 and not rows[0].granted
        assert "bf-used" not in rows[0].pseudonym
        dry = await backfill_beta_access(db, rows=rows, apply=False, run_label="t")
        await db.commit()
    assert (dry.candidates, dry.granted) == (1, 0)

    async with sessionmaker() as db:
        rows = await collect_usage(db, secret="s3cret")
        assert not rows[0].granted
        applied = await backfill_beta_access(db, rows=rows, apply=True, run_label="t")
        await db.commit()
    assert (applied.candidates, applied.granted) == (1, 1)

    async with sessionmaker() as db:
        rows = await collect_usage(db, secret="s3cret")
        assert rows[0].granted
        repeat = await backfill_beta_access(db, rows=rows, apply=True, run_label="t")
        await db.commit()
        events = (
            (
                await db.execute(
                    select(AdminAuditEvent).where(AdminAuditEvent.action == "BETA_ACCESS_GRANTED")
                )
            )
            .scalars()
            .all()
        )
    assert (repeat.candidates, repeat.granted, repeat.already_granted) == (0, 0, 1)
    assert len(events) == 1 and events[0].actor_user_id is None
    assert events[0].safe_metadata["source"] == "cli_backfill"
