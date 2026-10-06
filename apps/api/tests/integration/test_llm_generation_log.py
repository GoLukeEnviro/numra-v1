"""Phase 6b / F07a: PII-sicheres LLM-Nutzungslog fuer die Quelle `report`.

Geschrieben wird nur Metadaten (Quelle, Modell, Status, Versuch, Latenz, optionale
Provider-Tokens, Prompt-Hash) -- nie Prompt, Antwort oder Fehlertext. Das Log darf den
Nutzerpfad (Report-Job) in keinem Fall scheitern lassen.
"""

from __future__ import annotations

import logging
import re
import uuid

import pytest
from sqlalchemy import inspect, select, text

from numra_api.auth.passwords import hash_password
from numra_api.models import LLMGeneration, ReportJob
from numra_api.models.enums import ReportJobStatus
from numra_api.repositories.users import create_user
from numra_api.services.llm_generation_log import record
from numra_api.worker import run_one_cycle
from numra_interpretation.llm.errors import LLMProviderTimeout, LLMProviderUnavailable
from numra_interpretation.llm.mock_provider import MockLLMProvider

pytestmark = pytest.mark.integration

_EXPECTED_COLUMNS = {
    "id",
    "report_job_id",
    "source",
    "provider",
    "model",
    "status",
    "attempt",
    "latency_ms",
    "prompt_tokens",
    "completion_tokens",
    "total_tokens",
    "prompt_hash",
    "section_id",
    "error_code",
    "created_at",
}


class _CountingProvider:
    """Mock-Delegat mit Provider-/Modellnamen; scheitert optional fuer die ersten
    ``fail_times`` Aufrufe von `generate_structured` mit ``error``."""

    provider_name = "fake-provider"
    premium_model = "fake-premium"
    fast_model = "fake-fast"

    def __init__(self, *, fail_times: int = 0, error: Exception | None = None) -> None:
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
        if self._error is not None and self.calls <= self._fail_times:
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


async def _create_report_job(client, sessionmaker, lukas_payload, *, email: str) -> uuid.UUID:
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
    return uuid.UUID(report["job_id"])


async def _rows(sessionmaker) -> list[LLMGeneration]:
    async with sessionmaker() as db:
        result = await db.execute(select(LLMGeneration).order_by(LLMGeneration.created_at))
        return list(result.scalars())


async def _job(sessionmaker, job_id: uuid.UUID) -> ReportJob:
    async with sessionmaker() as db:
        return (await db.execute(select(ReportJob).where(ReportJob.id == job_id))).scalar_one()


async def _clear_backoff(sessionmaker, job_id: uuid.UUID) -> None:
    async with sessionmaker() as db:
        job = (await db.execute(select(ReportJob).where(ReportJob.id == job_id))).scalar_one()
        job.next_attempt_at = None
        await db.commit()


async def test_success_writes_one_ok_row_per_provider_call(
    client, sessionmaker, lukas_payload
) -> None:
    job_id = await _create_report_job(client, sessionmaker, lukas_payload, email="g-ok@x.de")
    provider = _CountingProvider()

    await run_one_cycle(sessionmaker, llm=provider)

    rows = await _rows(sessionmaker)
    assert provider.calls > 0
    assert len(rows) == provider.calls
    for row in rows:
        assert row.source == "report"
        assert row.status == "ok"
        assert row.attempt == 1
        assert row.report_job_id == job_id
        assert row.provider == "fake-provider"
        assert row.model == "fake-premium"
        assert row.error_code is None
        assert row.latency_ms is not None and row.latency_ms >= 0
        assert re.fullmatch(r"[0-9a-f]{64}", row.prompt_hash)
    assert any(row.section_id for row in rows)


async def test_tokens_stay_null_when_the_provider_reports_none(
    client, sessionmaker, lukas_payload
) -> None:
    await _create_report_job(client, sessionmaker, lukas_payload, email="g-tok@x.de")
    await run_one_cycle(sessionmaker, llm=_CountingProvider())

    rows = await _rows(sessionmaker)
    assert rows
    for row in rows:
        assert row.prompt_tokens is None
        assert row.completion_tokens is None
        assert row.total_tokens is None


async def test_provider_failure_without_retry_writes_error_row_without_message(
    client, sessionmaker, lukas_payload
) -> None:
    job_id = await _create_report_job(client, sessionmaker, lukas_payload, email="g-err@x.de")
    provider = _CountingProvider(
        fail_times=99,
        error=LLMProviderUnavailable("SECRET-LEAK-SENTINEL", retryable=False),
    )

    await run_one_cycle(sessionmaker, llm=provider)

    assert (await _job(sessionmaker, job_id)).status == ReportJobStatus.FAILED
    rows = await _rows(sessionmaker)
    assert len(rows) == 1
    row = rows[0]
    assert (row.status, row.error_code, row.attempt) == ("error", "LLMProviderUnavailable", 1)
    assert row.latency_ms is not None
    assert "SECRET-LEAK-SENTINEL" not in repr(
        {c.name: getattr(row, c.name) for c in LLMGeneration.__table__.columns}
    )


async def test_retryable_failure_then_success_records_retry_and_attempts(
    client, sessionmaker, lukas_payload
) -> None:
    job_id = await _create_report_job(client, sessionmaker, lukas_payload, email="g-retry@x.de")
    provider = _CountingProvider(fail_times=1, error=LLMProviderTimeout("boom"))

    await run_one_cycle(sessionmaker, llm=provider)
    first = await _rows(sessionmaker)
    assert [(r.status, r.attempt, r.error_code) for r in first] == [
        ("retry", 1, "LLMProviderTimeout")
    ]

    await _clear_backoff(sessionmaker, job_id)
    await run_one_cycle(sessionmaker, llm=provider)

    rows = await _rows(sessionmaker)
    later = rows[1:]
    assert later and all(r.status == "ok" and r.attempt == 2 for r in later)
    assert (await _job(sessionmaker, job_id)).status == ReportJobStatus.COMPLETE


async def test_account_deletion_removes_the_generation_rows(
    client, sessionmaker, lukas_payload
) -> None:
    """Retention-Matrix: `llm_generations` haengt per ON DELETE CASCADE an `report_jobs`
    und geht mit der Account-Loeschung mit (kein eigener DELETE noetig)."""
    email = "g-del@x.de"
    await _create_report_job(client, sessionmaker, lukas_payload, email=email)
    await run_one_cycle(sessionmaker, llm=_CountingProvider())
    assert await _rows(sessionmaker)

    response = await client.post(
        "/v1/account/delete-all",
        json={"password": "password12345"},
        headers={"x-csrf-token": client.cookies["numra_csrf"]},
    )
    assert response.status_code == 204

    assert await _rows(sessionmaker) == []


async def test_record_failure_never_breaks_the_caller_but_is_logged(
    client, sessionmaker, lukas_payload, caplog
) -> None:
    job_id = await _create_report_job(client, sessionmaker, lukas_payload, email="g-safe@x.de")
    common = {
        "provider": "p",
        "model": "m",
        "attempt": 1,
        "prompt_hash": "0" * 64,
        "report_job_id": job_id,
    }
    async with sessionmaker() as db:
        job = (await db.execute(select(ReportJob).where(ReportJob.id == job_id))).scalar_one()
        job.progress = 42  # ausstehende Nutzerpfad-Arbeit in derselben Transaktion

        with caplog.at_level(logging.ERROR, logger="numra_api.llm_generation_log"):
            ok_bad = await record(db, source="bogus", status="ok", **common)  # type: ignore[arg-type]
        assert ok_bad is False
        assert any(r.levelno == logging.ERROR for r in caplog.records)

        assert await record(db, source="report", status="ok", **common) is True
        await db.commit()

    assert (await _job(sessionmaker, job_id)).progress == 42
    assert len(await _rows(sessionmaker)) == 1


async def test_record_stores_provider_tokens_verbatim(client, sessionmaker, lukas_payload) -> None:
    job_id = await _create_report_job(client, sessionmaker, lukas_payload, email="g-tv@x.de")
    async with sessionmaker() as db:
        await record(
            db,
            source="report",
            provider="p",
            model="m",
            status="ok",
            attempt=1,
            prompt_hash="1" * 64,
            report_job_id=job_id,
            prompt_tokens=11,
            completion_tokens=7,
            total_tokens=18,
        )
        await db.commit()
    (row,) = await _rows(sessionmaker)
    assert (row.prompt_tokens, row.completion_tokens, row.total_tokens) == (11, 7, 18)


async def test_schema_has_no_prompt_or_text_columns_and_cascades_from_report_job(
    db_engine,
) -> None:
    def introspect(sync_conn):
        insp = inspect(sync_conn)
        return insp.get_columns("llm_generations"), insp.get_foreign_keys("llm_generations")

    async with db_engine.connect() as conn:
        columns, fks = await conn.run_sync(introspect)

    assert {c["name"] for c in columns} == _EXPECTED_COLUMNS
    for column in columns:
        assert "TEXT" not in str(column["type"]).upper(), column["name"]
        assert "JSON" not in str(column["type"]).upper(), column["name"]
    for name in ("prompt_tokens", "completion_tokens", "total_tokens", "latency_ms"):
        assert next(c for c in columns if c["name"] == name)["nullable"] is True
    (fk,) = fks
    assert fk["referred_table"] == "report_jobs"
    assert fk["options"].get("ondelete") == "CASCADE"


async def test_check_constraints_reject_unknown_source_and_status(db_engine) -> None:
    insert = text(
        "INSERT INTO llm_generations (id, source, provider, model, status, attempt, prompt_hash)"
        " VALUES (gen_random_uuid(), :source, 'p', 'm', :status, 1, 'h')"
    )
    async with db_engine.begin() as conn:
        await conn.execute(insert, {"source": "copilot", "status": "retry"})
    for source, status in (("other", "ok"), ("report", "OK")):
        with pytest.raises(Exception, match="ck_llm_generations"):
            async with db_engine.begin() as conn:
                await conn.execute(insert, {"source": source, "status": status})
