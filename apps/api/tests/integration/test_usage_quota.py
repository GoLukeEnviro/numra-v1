"""D4 quotas: atomic counting under parallelism, retries/idempotency, failure refund,
concurrency limit, every entry point, and "no limit configured = nothing happens"."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select
from test_copilot_threads import _connect as _copilot_connect
from test_copilot_threads import _create_thread as _copilot_thread
from test_copilot_threads import _post_message as _copilot_post
from test_evidence_results import _create_person, _login
from test_personal_copilot_threads import (
    _create_personal_thread,
    _personal_user,
    _post_personal_message,
)
from test_relationship_analysis import _set_up_partner_workspace
from test_report_retry import _clear_backoff, _FlakyProvider, _ScaffoldingProvider

from numra_api.models import Report, UsageReservation
from numra_api.worker import run_one_cycle
from numra_interpretation.llm.errors import LLMProviderUnavailable

pytestmark = pytest.mark.integration

REPORT_BODY_KEYS = ("calculation_id", "report_type")


@pytest.fixture
def limits(app, settings):
    def _apply(**kwargs):
        app.state.settings = settings.model_copy(update=kwargs)

    return _apply


async def _rows(sessionmaker, feature: str | None = None) -> list[UsageReservation]:
    async with sessionmaker() as db:
        stmt = select(UsageReservation).order_by(UsageReservation.created_at)
        if feature:
            stmt = stmt.where(UsageReservation.feature == feature)
        return list((await db.execute(stmt)).scalars().all())


async def _calculation_id(client, headers, payload) -> str:
    person = (await client.post("/v1/people", json=payload, headers=headers)).json()
    calc = (
        await client.post(
            f"/v1/people/{person['id']}/calculations",
            json={"as_of_date": "2026-01-01"},
            headers=headers,
        )
    ).json()
    return calc["id"]


def _post_report(client, headers, calc_id, **extra):
    return client.post(
        "/v1/reports",
        json={"calculation_id": calc_id, "report_type": "QUICK"},
        headers={**headers, **extra},
    )


async def test_without_limits_nothing_is_counted_or_written(
    client, sessionmaker, lukas_payload
) -> None:
    headers = await _login(client, sessionmaker, "q-off@example.com")
    calc_id = await _calculation_id(client, headers, lukas_payload)
    for _ in range(6):
        assert (await _post_report(client, headers, calc_id)).status_code == 201
    assert await _rows(sessionmaker) == []


async def test_window_limit_returns_429_with_retry_information(
    client, sessionmaker, lukas_payload, limits
) -> None:
    limits(quota_report_max=2, quota_report_window_seconds=3600)
    headers = await _login(client, sessionmaker, "q-window@example.com")
    calc_id = await _calculation_id(client, headers, lukas_payload)
    assert (await _post_report(client, headers, calc_id)).status_code == 201
    assert (await _post_report(client, headers, calc_id)).status_code == 201

    denied = await _post_report(client, headers, calc_id)

    assert denied.status_code == 429
    body = denied.json()
    assert body["code"] == "QUOTA_EXCEEDED"
    assert (body["feature"], body["limit_kind"], body["limit"]) == ("report", "window", 2)
    assert 1 <= body["retry_after_seconds"] <= 3600
    assert denied.headers["retry-after"] == str(body["retry_after_seconds"])
    assert len(await _rows(sessionmaker, "report")) == 2
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(Report))).scalar_one() == 2


async def test_twenty_parallel_requests_at_limit_five_yield_exactly_five(
    client, sessionmaker, lukas_payload, limits
) -> None:
    limits(quota_report_max=5)
    headers = await _login(client, sessionmaker, "q-parallel@example.com")
    calc_id = await _calculation_id(client, headers, lukas_payload)

    responses = await asyncio.gather(*[_post_report(client, headers, calc_id) for _ in range(20)])

    codes = sorted(r.status_code for r in responses)
    assert codes == [201] * 5 + [429] * 15
    assert len(await _rows(sessionmaker, "report")) == 5
    async with sessionmaker() as db:
        assert (await db.execute(select(func.count()).select_from(Report))).scalar_one() == 5


async def test_quota_is_per_user(client, sessionmaker, lukas_payload, limits) -> None:
    limits(quota_report_max=1)
    headers = await _login(client, sessionmaker, "q-user-a@example.com")
    calc_a = await _calculation_id(client, headers, lukas_payload)
    assert (await _post_report(client, headers, calc_a)).status_code == 201
    assert (await _post_report(client, headers, calc_a)).status_code == 429

    headers_b = await _login(client, sessionmaker, "q-user-b@example.com")
    calc_b = await _calculation_id(client, headers_b, lukas_payload)
    assert (await _post_report(client, headers_b, calc_b)).status_code == 201


async def test_same_idempotency_key_consumes_one_unit(
    client, sessionmaker, lukas_payload, limits
) -> None:
    limits(quota_report_max=1)
    headers = await _login(client, sessionmaker, "q-idem@example.com")
    calc_id = await _calculation_id(client, headers, lukas_payload)

    first = await _post_report(client, headers, calc_id, **{"Idempotency-Key": "k-1"})
    repeat = await _post_report(client, headers, calc_id, **{"Idempotency-Key": "k-1"})

    assert (first.status_code, repeat.status_code) == (201, 201)
    assert first.json()["job_id"] == repeat.json()["job_id"]
    assert len(await _rows(sessionmaker, "report")) == 1
    other = await _post_report(client, headers, calc_id, **{"Idempotency-Key": "k-2"})
    assert other.status_code == 429


async def test_terminally_failed_job_gives_its_unit_back(
    client, sessionmaker, lukas_payload, limits
) -> None:
    limits(quota_report_max=1)
    headers = await _login(client, sessionmaker, "q-refund@example.com")
    calc_id = await _calculation_id(client, headers, lukas_payload)
    assert (await _post_report(client, headers, calc_id)).status_code == 201
    assert (await _post_report(client, headers, calc_id)).status_code == 429

    class _Broken:
        async def health(self):  # pragma: no cover - not used
            raise NotImplementedError

        async def generate(self, request):
            raise RuntimeError("boom")

        async def generate_structured(self, request, schema):
            raise RuntimeError("boom")

    await run_one_cycle(sessionmaker, llm=_Broken())

    states = [r.state for r in await _rows(sessionmaker, "report")]
    assert states == ["released"]
    assert (await _post_report(client, headers, calc_id)).status_code == 201


async def test_worker_retry_keeps_one_reservation_and_success_settles_it(
    client, sessionmaker, lukas_payload, limits, llm
) -> None:
    limits(quota_report_max=1)
    headers = await _login(client, sessionmaker, "q-retry@example.com")
    calc_id = await _calculation_id(client, headers, lukas_payload)
    job_id = (await _post_report(client, headers, calc_id)).json()["job_id"]

    flaky = _FlakyProvider(fail_times=1, error=LLMProviderUnavailable("down"))
    await run_one_cycle(sessionmaker, llm=flaky)
    assert [r.state for r in await _rows(sessionmaker, "report")] == ["active"]

    from sqlalchemy import update

    from numra_api.models import ReportJob

    async with sessionmaker() as db:
        await db.execute(update(ReportJob).values(next_attempt_at=None))
        await db.commit()
    await run_one_cycle(sessionmaker, llm=llm)

    rows = await _rows(sessionmaker, "report")
    assert [(str(r.ref_id), r.state) for r in rows] == [(job_id, "settled")]
    # a settled unit still counts for the window
    assert (await _post_report(client, headers, calc_id)).status_code == 429


async def test_concurrent_limit_blocks_until_the_job_finished(
    client, sessionmaker, lukas_payload, limits, llm
) -> None:
    limits(quota_report_max_concurrent=1)
    headers = await _login(client, sessionmaker, "q-conc@example.com")
    calc_id = await _calculation_id(client, headers, lukas_payload)
    assert (await _post_report(client, headers, calc_id)).status_code == 201

    blocked = await _post_report(client, headers, calc_id)
    assert blocked.status_code == 429
    assert blocked.json()["limit_kind"] == "concurrent"
    assert blocked.json()["retry_after_seconds"] > 0

    await run_one_cycle(sessionmaker, llm=llm)

    assert (await _post_report(client, headers, calc_id)).status_code == 201


async def test_stale_active_reservation_stops_blocking(
    client, sessionmaker, lukas_payload, limits
) -> None:
    limits(quota_report_max_concurrent=1, quota_active_stale_seconds=60)
    headers = await _login(client, sessionmaker, "q-stale@example.com")
    calc_id = await _calculation_id(client, headers, lukas_payload)
    assert (await _post_report(client, headers, calc_id)).status_code == 201
    assert (await _post_report(client, headers, calc_id)).status_code == 429

    from sqlalchemy import text

    async with sessionmaker() as db:
        await db.execute(
            text("UPDATE usage_reservations SET created_at = now() - interval '2 hours'")
        )
        await db.commit()

    assert (await _post_report(client, headers, calc_id)).status_code == 201


async def test_beta_gate_is_checked_before_quota(
    client, sessionmaker, lukas_payload, limits
) -> None:
    limits(quota_report_max=1, beta_gate_enforced=True)
    headers = await _login(client, sessionmaker, "q-gate@example.com")
    response = await client.post(
        "/v1/reports",
        json={"calculation_id": "00000000-0000-4000-8000-000000000001", "report_type": "QUICK"},
        headers=headers,
    )
    assert response.status_code == 403 and response.json()["code"] == "BETA_ACCESS_REQUIRED"
    assert await _rows(sessionmaker) == []


async def test_relationship_and_shadow_share_the_analysis_budget(
    client, sessionmaker, lukas_payload, limits
) -> None:
    limits(quota_analysis_max=1)
    workspace_id, headers_a, _ = await _set_up_partner_workspace(
        client, sessionmaker, lukas_payload, "q-ana-a@example.com", "q-ana-b@example.com"
    )
    ok = await client.post(
        f"/v1/workspaces/{workspace_id}/relationship-analysis", json={}, headers=headers_a
    )
    denied = await client.post(
        f"/v1/workspaces/{workspace_id}/shadow-dynamics", json={}, headers=headers_a
    )
    assert ok.status_code == 201
    assert denied.status_code == 429 and denied.json()["feature"] == "analysis"
    assert len(await _rows(sessionmaker, "analysis")) == 1


async def test_pattern_analysis_is_free_of_gate_and_quota(
    client, sessionmaker, lukas_payload, limits
) -> None:
    """Rein rechnerisch (kein LLM): weder Beta-Gate noch Analyse-Budget."""
    limits(quota_analysis_max=1, beta_gate_enforced=True)
    headers = await _login(client, sessionmaker, "q-pattern@example.com")
    person_id = await _create_person(client, headers, lukas_payload)
    body = {
        "metric_key": "energy",
        "correlation_target": "PERSONAL_DAY",
        "correlation_target_value": 1,
    }
    for _ in range(3):
        response = await client.post(
            f"/v1/people/{person_id}/pattern-analyses", json=body, headers=headers
        )
        assert response.status_code == 201
    assert await _rows(sessionmaker, "analysis") == []


async def test_window_slides_old_units_stop_counting(
    client, sessionmaker, lukas_payload, limits
) -> None:
    limits(quota_report_max=1, quota_report_window_seconds=3600)
    headers = await _login(client, sessionmaker, "q-slide@example.com")
    calc_id = await _calculation_id(client, headers, lukas_payload)
    assert (await _post_report(client, headers, calc_id)).status_code == 201
    denied = await _post_report(client, headers, calc_id)
    assert denied.status_code == 429

    from sqlalchemy import text

    async with sessionmaker() as db:
        await db.execute(
            text("UPDATE usage_reservations SET created_at = now() - interval '2 hours'")
        )
        await db.commit()

    assert (await _post_report(client, headers, calc_id)).status_code == 201


async def test_workspace_copilot_route_is_limited(client, sessionmaker, limits) -> None:
    limits(quota_copilot_max=1)
    workspace_id, _connection_id = await _copilot_connect(
        client, sessionmaker, "q-wschat-a@example.com", "q-wschat-b@example.com"
    )
    headers = {"x-csrf-token": client.cookies["numra_csrf"]}
    thread = await _copilot_thread(client, workspace_id, headers, "RELATIONSHIP_SHARED")
    first = await _copilot_post(client, workspace_id, thread["id"], headers, "Hallo?")
    second = await _copilot_post(client, workspace_id, thread["id"], headers, "Nochmal?")
    assert (first.status_code, second.status_code) == (201, 429)
    assert second.json()["feature"] == "copilot"


async def test_copilot_messages_are_limited_and_parallel_safe(client, sessionmaker, limits) -> None:
    limits(quota_copilot_max=3)
    headers = await _personal_user(client, sessionmaker, "q-chat@example.com", "Chatty")
    thread = await _create_personal_thread(client, headers)

    responses = await asyncio.gather(
        *[_post_personal_message(client, thread["id"], headers, f"Frage {i}") for i in range(10)]
    )

    assert sorted(r.status_code for r in responses) == [201] * 3 + [429] * 7
    assert [r.state for r in await _rows(sessionmaker, "copilot")] == ["settled"] * 3


async def test_failed_copilot_reply_hands_the_unit_back(client, sessionmaker, limits, app) -> None:
    limits(quota_copilot_max=1)
    headers = await _personal_user(client, sessionmaker, "q-chat-fail@example.com", "Chatty")
    thread = await _create_personal_thread(client, headers)
    healthy = app.state.llm_provider
    app.state.llm_provider = _FlakyProvider(fail_times=99, error=LLMProviderUnavailable("down"))

    failed = await _post_personal_message(client, thread["id"], headers, "Hallo?")

    assert failed.status_code == 201
    assert failed.json()["assistant_message"]["status"] == "FAILED"
    assert [r.state for r in await _rows(sessionmaker, "copilot")] == ["released"]

    app.state.llm_provider = healthy
    assert (
        await _post_personal_message(client, thread["id"], headers, "Nochmal")
    ).status_code == 201
    assert (
        await _post_personal_message(client, thread["id"], headers, "Und noch")
    ).status_code == 429


async def test_persistence_gate_rejection_hands_the_unit_back(
    client, sessionmaker, lukas_payload, limits
) -> None:
    """#315's persistence gate rejects scaffolding output as a retryable generation error;
    once the attempts are used up the job fails terminally and the unit comes back."""
    limits(quota_report_max=1)
    headers = await _login(client, sessionmaker, "q-gate-reject@example.com")
    calc_id = await _calculation_id(client, headers, lukas_payload)
    job_id = (await _post_report(client, headers, calc_id)).json()["job_id"]
    assert (await _post_report(client, headers, calc_id)).status_code == 429

    provider = _ScaffoldingProvider()
    for _ in range(5):
        await run_one_cycle(sessionmaker, llm=provider)
        await _clear_backoff(sessionmaker, job_id)
        if [r.state for r in await _rows(sessionmaker, "report")] != ["active"]:
            break

    assert [r.state for r in await _rows(sessionmaker, "report")] == ["released"]
    assert (await _post_report(client, headers, calc_id)).status_code == 201
