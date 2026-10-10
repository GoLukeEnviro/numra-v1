"""D6 (2/2): explicit, linked regeneration of flagged reports and relationship analyses.

The original is never changed; the new version is created through the normal job path
(beta gate, quota, persistence gate). A double click yields one version."""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from test_content_flag import (
    _complete_analysis,
    _complete_report,
    _login,
    _poison_analysis,
    _poison_report,
    _stored_content,
    _switch_user,
)
from test_report_retry import _clear_backoff

from numra_api.analysis_worker import run_one_cycle as run_analysis_cycle
from numra_api.auth.passwords import hash_password
from numra_api.models import AnalysisJob, RelationshipAnalysis, Report, ReportJob, UsageReservation
from numra_api.models.enums import UserRole
from numra_api.repositories.entitlements import grant_beta_access
from numra_api.repositories.reports import MAX_ATTEMPTS
from numra_api.repositories.users import create_user, set_user_role
from numra_api.services import relationship_analysis_service, report_service
from numra_api.worker import run_one_cycle

pytestmark = pytest.mark.integration


@pytest.fixture
def limits(app, settings):
    def _apply(**kwargs):
        app.state.settings = settings.model_copy(update=kwargs)

    return _apply


async def _flagged_report(client, sessionmaker, llm, payload, email: str):
    headers = await _login(client, sessionmaker, email)
    report_id = await _complete_report(client, sessionmaker, llm, headers, payload)
    await _poison_report(sessionmaker, report_id)
    return report_id, headers


async def _reports(sessionmaker) -> list[Report]:
    async with sessionmaker() as db:
        return list((await db.execute(select(Report).order_by(Report.created_at))).scalars())


async def _reservations(sessionmaker, feature: str) -> list[UsageReservation]:
    async with sessionmaker() as db:
        stmt = select(UsageReservation).where(UsageReservation.feature == feature)
        return list((await db.execute(stmt)).scalars())


def _regenerate(client, report_id: str, headers: dict, key: str | None = None):
    sent = {**headers, "Idempotency-Key": key} if key else headers
    return client.post(f"/v1/reports/{report_id}/regenerate", headers=sent)


# --- reports: happy path, link, original untouched ------------------------------------


async def test_regeneration_creates_a_linked_new_version_and_keeps_the_original(
    client, sessionmaker, llm, lukas_payload
) -> None:
    report_id, headers = await _flagged_report(
        client, sessionmaker, llm, lukas_payload, "regen-ok@example.com"
    )
    original = await _stored_content(sessionmaker, report_id)

    response = await _regenerate(client, report_id, headers)

    assert response.status_code == 201
    new = response.json()
    assert new["id"] != report_id
    assert new["regenerated_from_id"] == report_id
    assert new["status"] == "PENDING"

    assert await run_one_cycle(sessionmaker, llm=llm) is True
    done = (await client.get(f"/v1/reports/{new['id']}")).json()
    assert done["status"] == "COMPLETE"
    assert done["content_flag"] == "none"

    kept = (await client.get(f"/v1/reports/{report_id}")).json()
    assert kept["content"] == original  # byte-identical, still flagged, not overwritten
    assert kept["content_flag"] == "unresolved_template_tokens"
    assert kept["regenerated_from_id"] is None
    assert await _stored_content(sessionmaker, report_id) == original
    assert len(await _reports(sessionmaker)) == 2


async def test_regeneration_of_an_unflagged_report_is_refused(
    client, sessionmaker, llm, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, "regen-clean@example.com")
    report_id = await _complete_report(client, sessionmaker, llm, headers, lukas_payload)

    response = await _regenerate(client, report_id, headers)

    assert response.status_code == 409
    assert response.json()["code"] == "CONTENT_NOT_FLAGGED"
    assert len(await _reports(sessionmaker)) == 1
    assert await _reservations(sessionmaker, "report") == []


# --- double click ---------------------------------------------------------------------


async def test_double_click_creates_exactly_one_version_and_one_unit(
    client, sessionmaker, llm, lukas_payload, limits
) -> None:
    report_id, headers = await _flagged_report(
        client, sessionmaker, llm, lukas_payload, "regen-double@example.com"
    )
    limits(quota_report_max=5)

    responses = await asyncio.gather(
        _regenerate(client, report_id, headers, key="k-1"),
        _regenerate(client, report_id, headers, key="k-2"),
        _regenerate(client, report_id, headers),
    )

    assert sorted(r.status_code for r in responses) == [200, 200, 201]
    assert len({r.json()["id"] for r in responses}) == 1
    regenerated = [r for r in await _reports(sessionmaker) if r.regenerated_from_id]
    assert len(regenerated) == 1
    assert len(await _reservations(sessionmaker, "report")) == 1
    async with sessionmaker() as db:
        jobs = (await db.execute(select(func.count()).select_from(ReportJob))).scalar_one()
    assert jobs == 2  # the original's job and the single regeneration job


async def test_replayed_idempotency_key_returns_the_same_version(
    client, sessionmaker, llm, lukas_payload
) -> None:
    report_id, headers = await _flagged_report(
        client, sessionmaker, llm, lukas_payload, "regen-key@example.com"
    )
    first = await _regenerate(client, report_id, headers, key="regen-key-1")
    again = await _regenerate(client, report_id, headers, key="regen-key-1")

    assert (first.status_code, again.status_code) == (201, 200)
    assert first.json()["id"] == again.json()["id"]


async def test_idempotency_key_of_another_request_is_a_conflict(
    client, sessionmaker, llm, lukas_payload
) -> None:
    report_id, headers = await _flagged_report(
        client, sessionmaker, llm, lukas_payload, "regen-conflict@example.com"
    )
    other_id = await _complete_report(
        client,
        sessionmaker,
        llm,
        headers,
        {**lukas_payload, "birth_first_names": "Zweit", "person_account_mode": "MANAGED_OTHER"},
    )
    await _poison_report(sessionmaker, other_id)
    assert (await _regenerate(client, report_id, headers, key="shared-key")).status_code == 201

    clash = await _regenerate(client, other_id, headers, key="shared-key")

    assert clash.status_code == 409
    assert clash.json()["code"] == "IDEMPOTENCY_KEY_CONFLICT"


async def test_database_allows_only_one_live_regeneration_per_original(
    client, sessionmaker, llm, lukas_payload
) -> None:
    report_id, headers = await _flagged_report(
        client, sessionmaker, llm, lukas_payload, "regen-index@example.com"
    )
    assert (await _regenerate(client, report_id, headers)).status_code == 201

    async with sessionmaker() as db:
        child = (
            await db.execute(select(Report).where(Report.regenerated_from_id.is_not(None)))
        ).scalar_one()
        db.add(
            Report(
                user_id=child.user_id,
                calculation_id=child.calculation_id,
                report_type=child.report_type,
                calculation_version=child.calculation_version,
                knowledge_version=child.knowledge_version,
                prompt_version=child.prompt_version,
                profile_snapshot=child.profile_snapshot,
                report_schema_version=child.report_schema_version,
                status="PENDING",
                regenerated_from_id=child.regenerated_from_id,
            )
        )
        with pytest.raises(IntegrityError):
            await db.flush()


# --- access matrix --------------------------------------------------------------------


async def test_foreign_user_admin_and_anonymous_get_no_preview_and_no_regeneration(
    client, sessionmaker, llm, lukas_payload
) -> None:
    report_id, _headers = await _flagged_report(
        client, sessionmaker, llm, lukas_payload, "regen-owner@example.com"
    )
    preview_url = f"/v1/reports/{report_id}/regenerate-preview"

    stranger = await _login(client, sessionmaker, "regen-stranger@example.com")
    assert (await client.get(preview_url)).status_code == 404
    assert (await _regenerate(client, report_id, stranger)).status_code == 404

    async with sessionmaker() as db:
        admin = await create_user(
            db, email="regen-admin@example.com", password_hash=hash_password("password12345")
        )
        await set_user_role(db, user=admin, role=UserRole.ADMIN)
        await db.commit()
    admin_headers = await _switch_user(client, "regen-admin@example.com")
    assert (await client.get(preview_url)).status_code == 404
    assert (await _regenerate(client, report_id, admin_headers)).status_code == 404

    assert (await client.post("/v1/auth/logout", headers=admin_headers)).status_code in (200, 204)
    assert (await client.get(preview_url)).status_code == 401
    # an anonymous POST is stopped by the CSRF check before authentication (as for creation)
    assert (await _regenerate(client, report_id, {})).status_code in (401, 403)
    assert len(await _reports(sessionmaker)) == 1


async def test_regeneration_requires_the_csrf_token(
    client, sessionmaker, llm, lukas_payload
) -> None:
    report_id, _headers = await _flagged_report(
        client, sessionmaker, llm, lukas_payload, "regen-csrf@example.com"
    )

    response = await _regenerate(client, report_id, {})

    assert response.status_code == 403
    assert len(await _reports(sessionmaker)) == 1


async def test_beta_gate_covers_preview_and_regeneration(
    client, sessionmaker, llm, lukas_payload, limits
) -> None:
    report_id, headers = await _flagged_report(
        client, sessionmaker, llm, lukas_payload, "regen-beta@example.com"
    )
    limits(beta_gate_enforced=True)

    denied = await _regenerate(client, report_id, headers)
    denied_preview = await client.get(f"/v1/reports/{report_id}/regenerate-preview")

    assert denied.status_code == denied_preview.status_code == 403
    assert denied.json()["code"] == "BETA_ACCESS_REQUIRED"
    assert len(await _reports(sessionmaker)) == 1

    async with sessionmaker() as db:
        from numra_api.repositories.users import get_user_by_email

        user = await get_user_by_email(db, email="regen-beta@example.com")
        await grant_beta_access(db, user_id=user.id)
        await db.commit()
    assert (await _regenerate(client, report_id, headers)).status_code == 201


# --- preview --------------------------------------------------------------------------


async def test_preview_describes_the_effect_and_starts_nothing(
    client, sessionmaker, llm, lukas_payload, limits
) -> None:
    report_id, headers = await _flagged_report(
        client, sessionmaker, llm, lukas_payload, "regen-preview@example.com"
    )
    limits(quota_report_max=3, quota_report_window_seconds=3600)

    preview = (await client.get(f"/v1/reports/{report_id}/regenerate-preview")).json()

    assert preview["can_regenerate"] is True
    assert preview["blocked_reason"] is None
    assert preview["content_flag"] == "unresolved_template_tokens"
    assert preview["uses_llm"] is True
    assert (preview["feature"], preview["units"], preview["original_kept"]) == ("report", 1, True)
    assert preview["quota"]["window_limit"] == 3
    assert preview["quota"]["used_in_window"] == 0
    assert preview["quota"]["would_exceed"] is False
    assert len(await _reports(sessionmaker)) == 1
    assert await _reservations(sessionmaker, "report") == []

    new_id = (await _regenerate(client, report_id, headers)).json()["id"]
    after = (await client.get(f"/v1/reports/{report_id}/regenerate-preview")).json()
    assert after["can_regenerate"] is False
    assert after["blocked_reason"] == "ALREADY_REGENERATED"
    assert after["existing_regeneration_id"] == new_id
    assert after["quota"]["used_in_window"] == 1


async def test_preview_of_an_unflagged_report_says_nothing_to_replace(
    client, sessionmaker, llm, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, "regen-preview-clean@example.com")
    report_id = await _complete_report(client, sessionmaker, llm, headers, lukas_payload)

    preview = (await client.get(f"/v1/reports/{report_id}/regenerate-preview")).json()

    assert (preview["can_regenerate"], preview["blocked_reason"]) == (False, "NOT_FLAGGED")
    assert preview["quota"] is None  # no limit configured


# --- quota and persistence gate -------------------------------------------------------


async def test_regeneration_consumes_quota_like_a_fresh_report(
    client, sessionmaker, llm, lukas_payload, limits
) -> None:
    report_id, headers = await _flagged_report(
        client, sessionmaker, llm, lukas_payload, "regen-quota@example.com"
    )
    second_id = await _complete_report(
        client,
        sessionmaker,
        llm,
        headers,
        {**lukas_payload, "birth_first_names": "Dritt", "person_account_mode": "MANAGED_OTHER"},
    )
    await _poison_report(sessionmaker, second_id)
    limits(quota_report_max=1)

    assert (await _regenerate(client, report_id, headers)).status_code == 201
    assert [r.state for r in await _reservations(sessionmaker, "report")] == ["active"]
    assert await run_one_cycle(sessionmaker, llm=llm) is True
    assert [r.state for r in await _reservations(sessionmaker, "report")] == ["settled"]

    blocked = await _regenerate(client, second_id, headers)

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "QUOTA_EXCEEDED"
    assert [
        r for r in await _reports(sessionmaker) if r.regenerated_from_id == uuid.UUID(second_id)
    ] == []


async def test_defective_result_never_completes_and_hands_the_unit_back(
    client, sessionmaker, llm, lukas_payload, limits, monkeypatch
) -> None:
    report_id, headers = await _flagged_report(
        client, sessionmaker, llm, lukas_payload, "regen-gate@example.com"
    )
    original = await _stored_content(sessionmaker, report_id)
    limits(quota_report_max=1)
    real = report_service.generate_report

    async def _poisoned(**kwargs):
        result = await real(**kwargs)
        sections = list(result.sections)
        sections[0] = sections[0].model_copy(update={"summary": "Rest {{metric:a:life_path}}."})
        return result.model_copy(update={"sections": type(result.sections)(sections)})

    monkeypatch.setattr(report_service, "generate_report", _poisoned)
    new = (await _regenerate(client, report_id, headers)).json()

    for _ in range(5):
        await run_one_cycle(sessionmaker, llm=llm)
        await _clear_backoff(sessionmaker, new["job_id"])
        job = (await client.get(f"/v1/report-jobs/{new['job_id']}")).json()
        if job["status"] == "FAILED":
            break

    failed = (await client.get(f"/v1/reports/{new['id']}")).json()
    assert failed["status"] == "FAILED"
    assert failed["content"] is None
    assert [r.state for r in await _reservations(sessionmaker, "report")] == ["released"]
    assert await _stored_content(sessionmaker, report_id) == original

    monkeypatch.setattr(report_service, "generate_report", real)
    retry = await _regenerate(client, report_id, headers)  # a FAILED version does not block
    assert retry.status_code == 201
    assert retry.json()["id"] != new["id"]


# --- relationship analyses ------------------------------------------------------------


def _ra_url(workspace_id: str, analysis_id: str, suffix: str) -> str:
    return f"/v1/workspaces/{workspace_id}/relationship-analysis/{analysis_id}/{suffix}"


async def test_analysis_regeneration_is_linked_and_keeps_the_original(
    client, sessionmaker, llm, lukas_payload
) -> None:
    workspace_id, analysis_id, headers = await _complete_analysis(
        client, sessionmaker, llm, lukas_payload, "regen-ra"
    )
    stored = await _poison_analysis(sessionmaker, analysis_id)

    preview = (await client.get(_ra_url(workspace_id, analysis_id, "regenerate-preview"))).json()
    assert preview["can_regenerate"] is True
    assert preview["feature"] == "analysis"

    response = await client.post(_ra_url(workspace_id, analysis_id, "regenerate"), headers=headers)
    assert response.status_code == 201
    new = response.json()
    assert new["regenerated_from_id"] == analysis_id
    assert await run_analysis_cycle(sessionmaker, llm=llm) is True

    done = (
        await client.get(f"/v1/workspaces/{workspace_id}/relationship-analysis/{new['id']}")
    ).json()
    assert done["status"] == "COMPLETE"
    assert done["content_flag"] == "none"
    kept = (
        await client.get(f"/v1/workspaces/{workspace_id}/relationship-analysis/{analysis_id}")
    ).json()
    assert kept["result"] == stored
    assert kept["content_flag"] == "unresolved_template_tokens"


async def test_analysis_double_click_and_unflagged_refusal(
    client, sessionmaker, llm, lukas_payload, limits
) -> None:
    workspace_id, analysis_id, headers = await _complete_analysis(
        client, sessionmaker, llm, lukas_payload, "regen-ra-dbl"
    )
    url = _ra_url(workspace_id, analysis_id, "regenerate")

    refused = await client.post(url, headers=headers)
    assert refused.status_code == 409
    assert refused.json()["code"] == "CONTENT_NOT_FLAGGED"

    await _poison_analysis(sessionmaker, analysis_id)
    limits(quota_analysis_max=5)
    responses = await asyncio.gather(
        client.post(url, headers={**headers, "Idempotency-Key": "a-1"}),
        client.post(url, headers={**headers, "Idempotency-Key": "a-2"}),
        client.post(url, headers=headers),
    )

    assert sorted(r.status_code for r in responses) == [200, 200, 201]
    assert len({r.json()["id"] for r in responses}) == 1
    async with sessionmaker() as db:
        linked = (
            await db.execute(
                select(func.count())
                .select_from(RelationshipAnalysis)
                .where(RelationshipAnalysis.regenerated_from_id.is_not(None))
            )
        ).scalar_one()
        jobs = (await db.execute(select(func.count()).select_from(AnalysisJob))).scalar_one()
    assert (linked, jobs) == (1, 2)
    assert len(await _reservations(sessionmaker, "analysis")) == 1


async def test_analysis_regeneration_access_and_consent_matrix(
    client, sessionmaker, llm, lukas_payload
) -> None:
    workspace_id, analysis_id, headers_a = await _complete_analysis(
        client, sessionmaker, llm, lukas_payload, "regen-ra-acl"
    )
    await _poison_analysis(sessionmaker, analysis_id)
    preview = _ra_url(workspace_id, analysis_id, "regenerate-preview")
    start = _ra_url(workspace_id, analysis_id, "regenerate")

    # unknown analysis id inside the workspace
    unknown = str(uuid.uuid4())
    assert (
        await client.get(_ra_url(workspace_id, unknown, "regenerate-preview"))
    ).status_code == 404
    assert (
        await client.post(_ra_url(workspace_id, unknown, "regenerate"), headers=headers_a)
    ).status_code == 404

    # non-member: 404, no flag information
    outsider = await _login(client, sessionmaker, "regen-ra-outsider@example.com")
    assert (await client.get(preview)).status_code == 404
    assert (await client.post(start, headers=outsider)).status_code == 404

    # a (global) admin who is not a member gets nothing either
    async with sessionmaker() as db:
        admin = await create_user(
            db, email="regen-ra-admin@example.com", password_hash=hash_password("password12345")
        )
        await set_user_role(db, user=admin, role=UserRole.ADMIN)
        await db.commit()
    admin_headers = await _switch_user(client, "regen-ra-admin@example.com")
    assert (await client.get(preview)).status_code == 404
    assert (await client.post(start, headers=admin_headers)).status_code == 404

    # consent revoked by the partner: the old analysis stays readable, but preview and
    # regeneration are closed and nothing is created
    headers_b = await _switch_user(client, "regen-ra-acl-b@example.com")
    revoke = await client.post(
        f"/v1/workspaces/{workspace_id}/consent/revoke",
        json={"scope": "RELATIONSHIP_INSIGHTS"},
        headers=headers_b,
    )
    assert revoke.status_code == 200
    headers_a = await _switch_user(client, "regen-ra-acl-a@example.com")
    for response in (await client.get(preview), await client.post(start, headers=headers_a)):
        assert response.status_code == 403
        assert response.json()["code"] == "CONSENT_NOT_GRANTED"
    assert (
        await client.get(f"/v1/workspaces/{workspace_id}/relationship-analysis/{analysis_id}")
    ).status_code == 200
    async with sessionmaker() as db:
        count = (
            await db.execute(select(func.count()).select_from(RelationshipAnalysis))
        ).scalar_one()
    assert count == 1
    assert await _reservations(sessionmaker, "analysis") == []


async def test_analysis_defective_result_never_completes(
    client, sessionmaker, llm, lukas_payload, limits, monkeypatch
) -> None:
    workspace_id, analysis_id, headers = await _complete_analysis(
        client, sessionmaker, llm, lukas_payload, "regen-ra-gate"
    )
    stored = await _poison_analysis(sessionmaker, analysis_id)
    limits(quota_analysis_max=1)
    real = relationship_analysis_service.generate_relationship_analysis

    async def _poisoned(**kwargs):
        result = await real(**kwargs)
        dimension = result.dimensions[0]
        statement = dimension.statements[0].model_copy(update={"canonical_refs": ("[a:foo]",)})
        dimension = dimension.model_copy(update={"statements": (statement,)})
        return result.model_copy(update={"dimensions": (dimension, *result.dimensions[1:])})

    monkeypatch.setattr(relationship_analysis_service, "generate_relationship_analysis", _poisoned)
    new = (
        await client.post(_ra_url(workspace_id, analysis_id, "regenerate"), headers=headers)
    ).json()

    assert await run_analysis_cycle(sessionmaker, llm=llm) is True
    async with sessionmaker() as db:
        await db.execute(
            update(AnalysisJob)
            .where(AnalysisJob.id == uuid.UUID(new["job_id"]))
            .values(next_attempt_at=None, attempt_count=MAX_ATTEMPTS - 1)
        )
        await db.commit()
    assert await run_analysis_cycle(sessionmaker, llm=llm) is True
    job = (await client.get(f"/v1/analysis-jobs/{new['job_id']}")).json()
    assert job["status"] == "FAILED"
    assert [r.state for r in await _reservations(sessionmaker, "analysis")] == ["released"]
    stored_new = (
        await client.get(f"/v1/workspaces/{workspace_id}/relationship-analysis/{new['id']}")
    ).json()
    assert stored_new["status"] != "COMPLETE"
    assert stored_new["result"] is None
    kept = (
        await client.get(f"/v1/workspaces/{workspace_id}/relationship-analysis/{analysis_id}")
    ).json()
    assert kept["result"] == stored


def _find_key(node, key):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                yield v
            yield from _find_key(v, key)
    elif isinstance(node, list):
        for item in node:
            yield from _find_key(item, key)


async def test_account_export_carries_the_regeneration_link(
    client, sessionmaker, llm, lukas_payload
) -> None:
    report_id, headers = await _flagged_report(
        client, sessionmaker, llm, lukas_payload, "regen-export@example.com"
    )
    assert (await _regenerate(client, report_id, headers)).status_code == 201

    exported = (await client.get("/v1/account/export")).json()

    links = [v for v in _find_key(exported, "regenerated_from_id") if v]
    assert links == [report_id]
