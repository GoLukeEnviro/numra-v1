"""Report job retry/error state machine (P0.2): a retryable failure must be requeued
(not marked FAILED, which `claim_next_job` never reclaims) with exponential backoff,
a non-retryable failure must fail terminally on the first attempt, an unexpected
exception must never crash the worker loop, and a job that eventually succeeds after
one or more retries must reach COMPLETE.
"""

from __future__ import annotations

import datetime as dt
import uuid

import pytest
from sqlalchemy import select

from numra_api.auth.passwords import hash_password
from numra_api.models import ReportJob
from numra_api.models.enums import ReportJobStatus
from numra_api.repositories.reports import claim_next_job
from numra_api.repositories.users import create_user
from numra_api.worker import run_one_cycle
from numra_interpretation.llm.errors import LLMProviderTimeout, LLMProviderUnavailable
from numra_interpretation.llm.mock_provider import MockLLMProvider

pytestmark = pytest.mark.integration


class _FlakyProvider:
    """Wraps `MockLLMProvider`, raising ``error`` from `generate_structured` for the
    first ``fail_times`` calls, then delegating to the real mock so the section
    eventually generates successfully."""

    def __init__(self, *, fail_times: int, error: Exception) -> None:
        self.calls = 0
        self._fail_times = fail_times
        self._error = error
        self._mock = MockLLMProvider()

    async def health(self):
        return await self._mock.health()

    async def generate(self, request):
        return await self._mock.generate(request)

    async def generate_structured(self, request, schema):
        self.calls += 1
        if self.calls <= self._fail_times:
            raise self._error
        return await self._mock.generate_structured(request, schema)


async def _login(client, sessionmaker, email: str) -> dict:
    async with sessionmaker() as db:
        await create_user(db, email=email, password_hash=hash_password("password12345"))
        await db.commit()
    response = await client.post(
        "/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert response.status_code == 200
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _create_report_job(
    client, sessionmaker, lukas_payload, *, email: str
) -> tuple[dict, str]:
    headers = await _login(client, sessionmaker, email)
    person = (await client.post("/v1/people", json=lukas_payload, headers=headers)).json()
    calc = (
        await client.post(
            f"/v1/people/{person['id']}/calculations",
            json={"as_of_date": "2026-01-01"},
            headers=headers,
        )
    ).json()
    report = (
        await client.post(
            "/v1/reports",
            json={"calculation_id": calc["id"], "report_type": "QUICK"},
            headers=headers,
        )
    ).json()
    return headers, report["job_id"]


async def _load_job(sessionmaker, job_id: str) -> ReportJob:
    async with sessionmaker() as db:
        result = await db.execute(select(ReportJob).where(ReportJob.id == uuid.UUID(job_id)))
        job = result.scalar_one()
        # Detach so attribute access after the session closes doesn't trigger a lazy
        # load / MissingGreenlet — the caller only reads plain columns.
        db.expunge(job)
        return job


async def _clear_backoff(sessionmaker, job_id: str) -> None:
    """Directly clear ``next_attempt_at`` so the next `run_one_cycle` can reclaim the
    job immediately instead of waiting out the real backoff delay."""
    async with sessionmaker() as db:
        result = await db.execute(select(ReportJob).where(ReportJob.id == uuid.UUID(job_id)))
        job = result.scalar_one()
        job.next_attempt_at = None
        await db.commit()


async def test_retryable_failure_is_requeued_not_failed(
    client, sessionmaker, lukas_payload
) -> None:
    _headers, job_id = await _create_report_job(
        client, sessionmaker, lukas_payload, email="retry-requeue@example.com"
    )
    provider = _FlakyProvider(fail_times=99, error=LLMProviderTimeout("simulated timeout"))

    claimed = await run_one_cycle(sessionmaker, llm=provider)
    assert claimed is True

    job = await _load_job(sessionmaker, job_id)
    assert job.status == ReportJobStatus.QUEUED
    assert job.attempt_count == 1
    assert job.next_attempt_at is not None
    assert job.error_code is not None and "LLM_PROVIDER_ERROR" in job.error_code

    async with sessionmaker() as db:
        from numra_api.models import Report

        result = await db.execute(select(Report).where(Report.id == job.report_id))
        report = result.scalar_one()
        assert report.status == "PENDING"


async def test_job_succeeds_after_one_retry(client, sessionmaker, lukas_payload) -> None:
    _headers, job_id = await _create_report_job(
        client, sessionmaker, lukas_payload, email="retry-success@example.com"
    )
    provider = _FlakyProvider(fail_times=1, error=LLMProviderTimeout("simulated timeout"))

    claimed_1 = await run_one_cycle(sessionmaker, llm=provider)
    assert claimed_1 is True
    job_after_first = await _load_job(sessionmaker, job_id)
    assert job_after_first.status == ReportJobStatus.QUEUED
    assert job_after_first.attempt_count == 1

    await _clear_backoff(sessionmaker, job_id)

    claimed_2 = await run_one_cycle(sessionmaker, llm=provider)
    assert claimed_2 is True
    job_after_second = await _load_job(sessionmaker, job_id)
    assert job_after_second.status == ReportJobStatus.COMPLETE
    assert job_after_second.attempt_count == 2
    assert provider.calls > 1


async def test_non_retryable_failure_fails_terminally_on_first_attempt(
    client, sessionmaker, lukas_payload
) -> None:
    _headers, job_id = await _create_report_job(
        client, sessionmaker, lukas_payload, email="retry-nonretryable@example.com"
    )
    provider = _FlakyProvider(
        fail_times=99, error=LLMProviderUnavailable("simulated permanent failure", retryable=False)
    )

    claimed = await run_one_cycle(sessionmaker, llm=provider)
    assert claimed is True

    job = await _load_job(sessionmaker, job_id)
    # Only one attempt was made even though MAX_ATTEMPTS=3 — non-retryable means no
    # retry is scheduled regardless of attempts remaining.
    assert job.status == ReportJobStatus.FAILED
    assert job.attempt_count == 1

    async with sessionmaker() as db:
        from numra_api.models import Report

        result = await db.execute(select(Report).where(Report.id == job.report_id))
        report = result.scalar_one()
        assert report.status == "FAILED"


async def test_retry_limit_exceeded_fails_terminally(client, sessionmaker, lukas_payload) -> None:
    _headers, job_id = await _create_report_job(
        client, sessionmaker, lukas_payload, email="retry-limit@example.com"
    )
    provider = _FlakyProvider(fail_times=99, error=LLMProviderTimeout("simulated timeout"))

    for _ in range(3):
        claimed = await run_one_cycle(sessionmaker, llm=provider)
        assert claimed is True
        await _clear_backoff(sessionmaker, job_id)

    job = await _load_job(sessionmaker, job_id)
    assert job.status == ReportJobStatus.FAILED
    assert job.attempt_count == 3
    assert job.error_code is not None and "LLM_PROVIDER_ERROR" in job.error_code

    # A further cycle must not reclaim the exhausted job.
    claimed_again = await run_one_cycle(sessionmaker, llm=provider)
    assert claimed_again is False


async def test_two_concurrent_workers_never_claim_the_same_job(
    client, sessionmaker, lukas_payload
) -> None:
    """SELECT ... FOR UPDATE SKIP LOCKED (master prompt §110): a second worker racing
    to claim while the first still holds the row locked (uncommitted) must be skipped,
    not handed the same job."""
    _headers, job_id = await _create_report_job(
        client, sessionmaker, lukas_payload, email="retry-concurrent@example.com"
    )

    now = dt.datetime.now(dt.UTC)
    async with sessionmaker() as db_a:
        job_a = await claim_next_job(db_a, now=now, lease_seconds=300)
        assert job_a is not None
        assert str(job_a.id) == job_id

        async with sessionmaker() as db_b:
            job_b = await claim_next_job(db_b, now=now, lease_seconds=300)
            assert job_b is None
            await db_b.commit()

        await db_a.commit()


async def test_unexpected_exception_does_not_crash_worker_loop(
    client, sessionmaker, lukas_payload
) -> None:
    _headers, job_id = await _create_report_job(
        client, sessionmaker, lukas_payload, email="retry-unexpected@example.com"
    )
    provider = _FlakyProvider(fail_times=99, error=RuntimeError("totally unexpected bug"))

    claimed = await run_one_cycle(sessionmaker, llm=provider)
    assert claimed is True

    job = await _load_job(sessionmaker, job_id)
    assert job.status == ReportJobStatus.FAILED
    assert job.error_code is not None and "UNEXPECTED_ERROR" in job.error_code

    # The worker loop itself must still be alive: the next cycle runs cleanly.
    claimed_again = await run_one_cycle(sessionmaker, llm=provider)
    assert claimed_again is False
