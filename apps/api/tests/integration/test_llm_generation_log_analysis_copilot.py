"""Phase 6b Teil 2: PII-sicheres LLM-Nutzungslog fuer die Quellen `analysis` (Analyse-Worker)
und `copilot` (persoenlich + Beziehung).

Pro Quelle: Erfolg, Provider-Fehler, Retry-Verhalten. Dazu Loesch-/Retentionsverhalten
(Account, Workspace-Loeschung, Dissolution) und die Zusage, dass das Logging den
Copilot-Nutzerpfad und den Analyse-Job nie scheitern laesst. Geschrieben wird nur
Metadaten -- nie Prompt, Antwort oder Fehlertext.
"""

from __future__ import annotations

import datetime as dt
import itertools
import logging
import re
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import inspect, select, text

from numra_api.analysis_worker import run_one_cycle
from numra_api.auth.passwords import hash_password
from numra_api.models import AnalysisJob, LLMGeneration
from numra_api.models.enums import AnalysisJobStatus
from numra_api.repositories.analysis import MAX_ATTEMPTS
from numra_api.repositories.users import create_user, mark_email_verified
from numra_api.services import llm_generation_log as log_module
from numra_interpretation.llm.errors import LLMProviderTimeout, LLMProviderUnavailable
from numra_interpretation.llm.mock_provider import MockLLMProvider

pytestmark = pytest.mark.integration

_PASSWORD = "password12345"
_SENTINEL = "SECRET-LEAK-SENTINEL"


class _Provider:
    """Mock-Delegat mit Provider-/Modellnamen. Die ersten ``fail_times`` Aufrufe von
    `generate_structured` scheitern mit ``error``; die ersten ``bad_reply_times``
    erfolgreichen Antworten bekommen einen ungueltigen `basis_type` (loest die
    Reparatur-Wiederholung der Copilot-Pipeline aus)."""

    provider_name = "fake-provider"
    premium_model = "fake-premium"
    fast_model = "fake-fast"

    def __init__(
        self, *, fail_times: int = 0, error: Exception | None = None, bad_reply_times: int = 0
    ) -> None:
        self.calls = 0
        self._fail_times = fail_times
        self._error = error
        self._bad_reply_times = bad_reply_times
        self._mock = MockLLMProvider()

    async def health(self):
        return await self._mock.health()

    async def generate(self, request):
        return await self._mock.generate(request)

    async def generate_structured(self, request, schema):
        self.calls += 1
        if self._error is not None and self.calls <= self._fail_times:
            raise self._error
        result = await self._mock.generate_structured(request, schema)
        if self.calls <= self._bad_reply_times and hasattr(result, "basis_type"):
            return result.model_copy(update={"basis_type": "BOGUS"})
        return result


# ---------------------------------------------------------------------------
# Setup-Helfer (je Testmodul dupliziert, wie im Rest der Suite)
# ---------------------------------------------------------------------------


async def _signup(client, sessionmaker, email: str) -> dict:
    async with sessionmaker() as db:
        user = await create_user(db, email=email, password_hash=hash_password(_PASSWORD))
        await mark_email_verified(db, user=user, verified_at=dt.datetime.now(dt.UTC))
        await db.commit()
    return await _switch_user(client, email)


async def _switch_user(client, email: str) -> dict:
    await client.post("/v1/auth/logout")
    response = await client.post("/v1/auth/login", json={"email": email, "password": _PASSWORD})
    assert response.status_code == 200, response.text[:300]
    return {"x-csrf-token": client.cookies["numra_csrf"]}


async def _create_self_person(client, headers: dict, payload: dict) -> None:
    response = await client.post("/v1/people", json=payload, headers=headers)
    assert response.status_code == 201
    calc = await client.post(
        f"/v1/people/{response.json()['id']}/calculations",
        json={"as_of_date": "2026-08-19"},
        headers=headers,
    )
    assert calc.status_code == 201


async def _personal_user(client, sessionmaker, lukas_payload, email: str) -> dict:
    headers = await _signup(client, sessionmaker, email)
    await _create_self_person(client, headers, lukas_payload)
    return headers


async def _workspace(client, sessionmaker, lukas_payload, tag: str) -> SimpleNamespace:
    """Zwei verbundene Konten (A laedt ein, B loest ein) mit SELF-Profil, Workspace-Typ
    PARTNER. Sitzung steht danach auf A."""
    email_a, email_b = f"{tag}-a@example.com", f"{tag}-b@example.com"
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
    await _create_self_person(client, headers_b, lukas_payload)
    headers_a = await _switch_user(client, email_a)
    await _create_self_person(
        client,
        headers_a,
        {**lukas_payload, "birth_first_names": "Partner", "birth_last_name": "Eins"},
    )
    workspace_id = redeem.json()["workspace_id"]
    patch = await client.patch(
        f"/v1/workspaces/{workspace_id}", json={"relationship_type": "PARTNER"}, headers=headers_a
    )
    assert patch.status_code == 200
    return SimpleNamespace(
        id=workspace_id,
        connection_id=redeem.json()["connection"]["id"],
        email_a=email_a,
        email_b=email_b,
    )


async def _analysis_job(client, workspace_id: str, headers: dict, path: str) -> uuid.UUID:
    response = await client.post(f"/v1/workspaces/{workspace_id}/{path}", json={}, headers=headers)
    assert response.status_code == 201, response.text[:300]
    return uuid.UUID(response.json()["job_id"])


async def _workspace_post(client, workspace_id: str, scope: str, headers: dict, content: str):
    thread = await client.post(
        f"/v1/workspaces/{workspace_id}/copilot/threads", json={"scope": scope}, headers=headers
    )
    assert thread.status_code == 201, thread.text[:300]
    return await client.post(
        f"/v1/workspaces/{workspace_id}/copilot/threads/{thread.json()['id']}/messages",
        json={"content": content},
        headers=headers,
    )


async def _personal_post(client, headers: dict, content: str):
    thread = await client.post("/v1/me/copilot/threads", json={}, headers=headers)
    assert thread.status_code == 201, thread.text[:300]
    return await client.post(
        f"/v1/me/copilot/threads/{thread.json()['id']}/messages",
        json={"content": content},
        headers=headers,
    )


async def _rows(sessionmaker, source: str | None = None) -> list[LLMGeneration]:
    async with sessionmaker() as db:
        stmt = select(LLMGeneration).order_by(LLMGeneration.created_at)
        if source is not None:
            stmt = stmt.where(LLMGeneration.source == source)
        return list((await db.execute(stmt)).scalars())


async def _clear_backoff(sessionmaker, job_id: uuid.UUID) -> None:
    async with sessionmaker() as db:
        job = (await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))).scalar_one()
        job.next_attempt_at = None
        await db.commit()


async def _job(sessionmaker, job_id: uuid.UUID) -> AnalysisJob:
    async with sessionmaker() as db:
        return (await db.execute(select(AnalysisJob).where(AnalysisJob.id == job_id))).scalar_one()


def _dump(row: LLMGeneration) -> str:
    return repr({c.name: getattr(row, c.name) for c in LLMGeneration.__table__.columns})


async def _delete_account(client, email: str) -> None:
    headers = await _switch_user(client, email)
    response = await client.post(
        "/v1/account/delete-all", json={"password": _PASSWORD}, headers=headers
    )
    assert response.status_code == 204, response.text[:300]


# ---------------------------------------------------------------------------
# Quelle analysis
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["relationship-analysis", "shadow-dynamics"])
async def test_analysis_success_writes_ok_rows_bound_to_the_job(
    client, sessionmaker, lukas_payload, path
) -> None:
    ws = await _workspace(client, sessionmaker, lukas_payload, f"an-ok-{path[:3]}")
    headers_a = await _switch_user(client, ws.email_a)
    job_id = await _analysis_job(client, ws.id, headers_a, path)
    provider = _Provider()

    assert await run_one_cycle(sessionmaker, llm=provider) is True

    assert (await _job(sessionmaker, job_id)).status == AnalysisJobStatus.COMPLETE
    rows = await _rows(sessionmaker)
    assert provider.calls > 0 and len(rows) == provider.calls
    for row in rows:
        assert row.source == "analysis"
        assert row.analysis_job_id == job_id
        assert row.report_job_id is None and row.chat_message_id is None
        assert (row.status, row.attempt, row.error_code) == ("ok", 1, None)
        assert (row.provider, row.model) == ("fake-provider", "fake-premium")
        assert row.latency_ms is not None and row.latency_ms >= 0
        assert re.fullmatch(r"[0-9a-f]{64}", row.prompt_hash)
        assert (row.prompt_tokens, row.completion_tokens, row.total_tokens) == (None, None, None)


async def test_analysis_provider_error_writes_error_row_without_message(
    client, sessionmaker, lukas_payload
) -> None:
    ws = await _workspace(client, sessionmaker, lukas_payload, "an-err")
    headers_a = await _switch_user(client, ws.email_a)
    job_id = await _analysis_job(client, ws.id, headers_a, "relationship-analysis")
    provider = _Provider(fail_times=99, error=LLMProviderUnavailable(_SENTINEL, retryable=False))

    await run_one_cycle(sessionmaker, llm=provider)

    assert (await _job(sessionmaker, job_id)).status == AnalysisJobStatus.FAILED
    (row,) = await _rows(sessionmaker)
    assert (row.source, row.status, row.attempt) == ("analysis", "error", 1)
    assert row.error_code == "LLMProviderUnavailable"
    assert row.analysis_job_id == job_id
    assert _SENTINEL not in _dump(row)


async def test_analysis_retryable_failure_records_retry_then_ok_with_next_attempt(
    client, sessionmaker, lukas_payload
) -> None:
    ws = await _workspace(client, sessionmaker, lukas_payload, "an-retry")
    headers_a = await _switch_user(client, ws.email_a)
    job_id = await _analysis_job(client, ws.id, headers_a, "relationship-analysis")
    provider = _Provider(fail_times=1, error=LLMProviderTimeout("boom"))

    await run_one_cycle(sessionmaker, llm=provider)
    assert [(r.status, r.attempt, r.error_code) for r in await _rows(sessionmaker)] == [
        ("retry", 1, "LLMProviderTimeout")
    ]

    await _clear_backoff(sessionmaker, job_id)
    await run_one_cycle(sessionmaker, llm=provider)

    later = (await _rows(sessionmaker))[1:]
    assert later and all(r.status == "ok" and r.attempt == 2 for r in later)
    assert all(r.analysis_job_id == job_id for r in later)
    assert (await _job(sessionmaker, job_id)).status == AnalysisJobStatus.COMPLETE


async def test_analysis_last_allowed_attempt_records_error_not_retry(
    client, sessionmaker, lukas_payload
) -> None:
    ws = await _workspace(client, sessionmaker, lukas_payload, "an-last")
    headers_a = await _switch_user(client, ws.email_a)
    job_id = await _analysis_job(client, ws.id, headers_a, "relationship-analysis")
    provider = _Provider(fail_times=99, error=LLMProviderTimeout("boom"))

    for _ in range(MAX_ATTEMPTS):
        await run_one_cycle(sessionmaker, llm=provider)
        await _clear_backoff(sessionmaker, job_id)

    rows = await _rows(sessionmaker)
    assert [(r.attempt, r.status) for r in rows] == [(1, "retry"), (2, "retry"), (3, "error")]
    assert (await _job(sessionmaker, job_id)).status == AnalysisJobStatus.FAILED


# ---------------------------------------------------------------------------
# Quelle copilot
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "scope", ["PERSONAL_PRIVATE", "RELATIONSHIP_SHARED", "RELATIONSHIP_PRIVATE"]
)
async def test_copilot_success_writes_ok_rows_bound_to_the_assistant_message(
    client, app, sessionmaker, lukas_payload, scope
) -> None:
    provider = _Provider()
    app.state.llm_provider = provider
    if scope == "PERSONAL_PRIVATE":
        headers = await _personal_user(client, sessionmaker, lukas_payload, "cp-ok-p@example.com")
        response = await _personal_post(client, headers, "Wie geht es mir?")
    else:
        ws = await _workspace(client, sessionmaker, lukas_payload, f"cp-ok-{scope[13:16].lower()}")
        headers = await _switch_user(client, ws.email_a)
        response = await _workspace_post(client, ws.id, scope, headers, "Wie geht es uns?")

    assert response.status_code == 201, response.text[:300]
    assistant = response.json()["assistant_message"]
    assert assistant["status"] == "COMPLETE"
    rows = await _rows(sessionmaker)
    assert provider.calls > 0 and len(rows) == provider.calls
    for row in rows:
        assert row.source == "copilot"
        assert str(row.chat_message_id) == assistant["id"]
        assert row.report_job_id is None and row.analysis_job_id is None
        assert (row.status, row.attempt, row.error_code) == ("ok", 1, None)
        assert (row.provider, row.model) == ("fake-provider", "fake-premium")
        assert row.latency_ms is not None and row.latency_ms >= 0
        assert re.fullmatch(r"[0-9a-f]{64}", row.prompt_hash)
        assert (row.prompt_tokens, row.completion_tokens, row.total_tokens) == (None, None, None)


async def test_copilot_provider_error_writes_error_row_and_failed_message_without_text(
    client, app, sessionmaker, lukas_payload
) -> None:
    app.state.llm_provider = _Provider(
        fail_times=99, error=LLMProviderUnavailable(_SENTINEL, retryable=False)
    )
    headers = await _personal_user(client, sessionmaker, lukas_payload, "cp-err@example.com")

    response = await _personal_post(client, headers, "Frage")

    assert response.status_code == 201, response.text[:300]
    assistant = response.json()["assistant_message"]
    assert (assistant["status"], assistant["error_code"]) == ("FAILED", "LLM_PROVIDER_ERROR")
    (row,) = await _rows(sessionmaker)
    assert (row.source, row.status, row.attempt) == ("copilot", "error", 1)
    assert row.error_code == "LLMProviderUnavailable"
    assert str(row.chat_message_id) == assistant["id"]
    assert _SENTINEL not in _dump(row) and _SENTINEL not in response.text


async def test_copilot_has_no_job_retry_so_retryable_error_is_error_and_resend_logs_ok(
    client, app, sessionmaker, lukas_payload
) -> None:
    """Der Copilot wiederholt nie selbst: ein retrybarer Fehler ist `error` (nie `retry`),
    die Wiederholung ist eine neue Nutzernachricht mit eigener ASSISTANT-Nachricht."""
    app.state.llm_provider = _Provider(fail_times=1, error=LLMProviderTimeout("boom"))
    headers = await _personal_user(client, sessionmaker, lukas_payload, "cp-retry@example.com")
    thread = (await client.post("/v1/me/copilot/threads", json={}, headers=headers)).json()
    url = f"/v1/me/copilot/threads/{thread['id']}/messages"

    first = await client.post(url, json={"content": "Frage"}, headers=headers)
    second = await client.post(url, json={"content": "Frage nochmal"}, headers=headers)

    assert first.json()["assistant_message"]["status"] == "FAILED"
    assert second.json()["assistant_message"]["status"] == "COMPLETE"
    rows = await _rows(sessionmaker)
    assert [(r.status, r.error_code, r.attempt) for r in rows] == [
        ("error", "LLMProviderTimeout", 1),
        ("ok", None, 1),
    ]
    assert str(rows[0].chat_message_id) == first.json()["assistant_message"]["id"]
    assert str(rows[1].chat_message_id) == second.json()["assistant_message"]["id"]


async def test_copilot_repair_call_is_logged_with_the_same_attempt_and_message(
    client, app, sessionmaker, lukas_payload
) -> None:
    provider = _Provider(bad_reply_times=1)
    app.state.llm_provider = provider
    headers = await _personal_user(client, sessionmaker, lukas_payload, "cp-fix@example.com")

    response = await _personal_post(client, headers, "Frage")

    assistant = response.json()["assistant_message"]
    assert assistant["status"] == "COMPLETE" and provider.calls == 2
    rows = await _rows(sessionmaker)
    assert [(r.status, r.attempt) for r in rows] == [("ok", 1), ("ok", 1)]
    assert {str(r.chat_message_id) for r in rows} == {assistant["id"]}


# ---------------------------------------------------------------------------
# Das Log darf den Nutzerpfad nie scheitern lassen
# ---------------------------------------------------------------------------


def _overflowing_clock(monkeypatch) -> None:
    """Latenz > int4: der INSERT scheitert beim Flush *im* SAVEPOINT von `record`."""
    ticks = itertools.count(0, 10**12)
    monkeypatch.setattr(log_module, "time", SimpleNamespace(perf_counter=lambda: next(ticks)))


async def test_copilot_reply_survives_a_failing_log_write(
    client, app, sessionmaker, lukas_payload, monkeypatch, caplog
) -> None:
    app.state.llm_provider = _Provider()
    headers = await _personal_user(client, sessionmaker, lukas_payload, "cp-safe@example.com")
    _overflowing_clock(monkeypatch)

    with caplog.at_level(logging.ERROR, logger="numra_api.llm_generation_log"):
        response = await _personal_post(client, headers, "Frage")

    assert response.status_code == 201, response.text[:300]
    body = response.json()
    assert body["assistant_message"]["status"] == "COMPLETE"
    assert body["user_message"]["status"] == "COMPLETE"
    assert await _rows(sessionmaker) == []
    assert any(r.levelno == logging.ERROR for r in caplog.records)


async def test_copilot_provider_error_survives_a_failing_log_write(
    client, app, sessionmaker, lukas_payload, monkeypatch, caplog
) -> None:
    app.state.llm_provider = _Provider(fail_times=99, error=LLMProviderTimeout("boom"))
    headers = await _personal_user(client, sessionmaker, lukas_payload, "cp-safe2@example.com")
    _overflowing_clock(monkeypatch)

    with caplog.at_level(logging.ERROR, logger="numra_api.llm_generation_log"):
        response = await _personal_post(client, headers, "Frage")

    assert response.status_code == 201, response.text[:300]
    assert response.json()["assistant_message"]["error_code"] == "LLM_PROVIDER_ERROR"
    assert await _rows(sessionmaker) == []
    assert any(r.levelno == logging.ERROR for r in caplog.records)


async def test_analysis_job_survives_a_failing_log_write(
    client, sessionmaker, lukas_payload, monkeypatch, caplog
) -> None:
    ws = await _workspace(client, sessionmaker, lukas_payload, "an-safe")
    headers_a = await _switch_user(client, ws.email_a)
    job_id = await _analysis_job(client, ws.id, headers_a, "relationship-analysis")
    _overflowing_clock(monkeypatch)

    with caplog.at_level(logging.ERROR, logger="numra_api.llm_generation_log"):
        await run_one_cycle(sessionmaker, llm=_Provider())

    assert (await _job(sessionmaker, job_id)).status == AnalysisJobStatus.COMPLETE
    assert await _rows(sessionmaker) == []
    assert any(r.levelno == logging.ERROR for r in caplog.records)


# ---------------------------------------------------------------------------
# Loeschung / Retention
# ---------------------------------------------------------------------------


async def _scoped_counts(sessionmaker) -> dict[str, int]:
    """Zeilenzahl je Herkunft: Analyse sowie Copilot nach Thread-Scope."""
    query = text(
        "SELECT CASE WHEN g.source = 'analysis' THEN 'analysis' ELSE t.scope END AS k, count(*)"
        " FROM llm_generations g"
        " LEFT JOIN chat_messages m ON m.id = g.chat_message_id"
        " LEFT JOIN chat_threads t ON t.id = m.thread_id GROUP BY 1"
    )
    async with sessionmaker() as db:
        return {k: n for k, n in (await db.execute(query)).all()}


async def _fill_workspace(client, app, sessionmaker, ws) -> None:
    """Je Quelle Zeilen: Analyse (von A), geteilter Thread (A), private Threads (A und B)."""
    app.state.llm_provider = _Provider()
    headers_a = await _switch_user(client, ws.email_a)
    await _analysis_job(client, ws.id, headers_a, "relationship-analysis")
    await run_one_cycle(sessionmaker, llm=_Provider())
    for scope in ("RELATIONSHIP_SHARED", "RELATIONSHIP_PRIVATE"):
        response = await _workspace_post(client, ws.id, scope, headers_a, "Frage A")
        assert response.json()["assistant_message"]["status"] == "COMPLETE"
    headers_b = await _switch_user(client, ws.email_b)
    response = await _workspace_post(client, ws.id, "RELATIONSHIP_PRIVATE", headers_b, "Frage B")
    assert response.json()["assistant_message"]["status"] == "COMPLETE"


async def test_account_deletion_removes_personal_copilot_rows(
    client, app, sessionmaker, lukas_payload
) -> None:
    """Persoenlicher Thread = privater Inhalt: Thread -> Nachrichten -> llm_generations
    gehen per Kaskade mit (kein eigener DELETE)."""
    app.state.llm_provider = _Provider()
    headers = await _personal_user(client, sessionmaker, lukas_payload, "del-p@example.com")
    assert (await _personal_post(client, headers, "Frage")).status_code == 201
    assert await _rows(sessionmaker, "copilot")

    await _delete_account(client, "del-p@example.com")

    assert await _rows(sessionmaker) == []


async def test_account_deletion_keeps_shared_history_rows_and_drops_private_ones(
    client, app, sessionmaker, lukas_payload
) -> None:
    """Retention-Matrix: private Threads der geloeschten Person weg (Kaskade), alles an
    geteilter Historie bleibt -- `analysis_jobs` (bewusst erhalten), der geteilte Thread und
    der private Thread des Partners."""
    ws = await _workspace(client, sessionmaker, lukas_payload, "del-m")
    await _fill_workspace(client, app, sessionmaker, ws)
    before = await _scoped_counts(sessionmaker)
    assert set(before) == {"analysis", "RELATIONSHIP_SHARED", "RELATIONSHIP_PRIVATE"}
    private_a = (
        await _count_private_rows(sessionmaker, ws.email_a),
        await _count_private_rows(sessionmaker, ws.email_b),
    )
    assert all(n > 0 for n in private_a)

    await _delete_account(client, ws.email_a)

    after = await _scoped_counts(sessionmaker)
    assert after["analysis"] == before["analysis"]
    assert after["RELATIONSHIP_SHARED"] == before["RELATIONSHIP_SHARED"]
    assert await _count_private_rows(sessionmaker, ws.email_a) == 0
    assert await _count_private_rows(sessionmaker, ws.email_b) == private_a[1]


async def _count_private_rows(sessionmaker, email: str) -> int:
    query = text(
        "SELECT count(*) FROM llm_generations g"
        " JOIN chat_messages m ON m.id = g.chat_message_id"
        " JOIN chat_threads t ON t.id = m.thread_id"
        " WHERE t.scope = 'RELATIONSHIP_PRIVATE'"
        " AND t.owner_user_id = (SELECT id FROM users WHERE email = :email)"
    )
    async with sessionmaker() as db:
        return int((await db.execute(query, {"email": email})).scalar_one())


async def test_workspace_hard_delete_cascades_analysis_and_copilot_rows(
    client, app, sessionmaker, lukas_payload
) -> None:
    ws = await _workspace(client, sessionmaker, lukas_payload, "del-ws")
    await _fill_workspace(client, app, sessionmaker, ws)
    assert await _scoped_counts(sessionmaker)

    async with sessionmaker() as db:
        await db.execute(
            text("DELETE FROM relationship_workspaces WHERE id = :id"), {"id": uuid.UUID(ws.id)}
        )
        await db.commit()

    assert await _rows(sessionmaker) == []


async def test_dissolution_keeps_rows_readable_and_blocks_new_workspace_copilot_rows(
    client, app, sessionmaker, lukas_payload
) -> None:
    """Dissolve ist ein Statuswechsel, kein Loeschen: geteilte Historie (und ihre
    Nutzungszeilen) bleibt; neue Workspace-Copilot-Nachrichten sind danach 409 und
    schreiben nichts."""
    ws = await _workspace(client, sessionmaker, lukas_payload, "dis")
    await _fill_workspace(client, app, sessionmaker, ws)
    before = await _scoped_counts(sessionmaker)
    async with sessionmaker() as db:
        shared_thread_id = (
            await db.execute(
                text(
                    "SELECT id FROM chat_threads WHERE workspace_id = :id"
                    " AND scope = 'RELATIONSHIP_SHARED'"
                ),
                {"id": uuid.UUID(ws.id)},
            )
        ).scalar_one()

    headers_b = await _switch_user(client, ws.email_b)
    dissolve = await client.post(f"/v1/connections/{ws.connection_id}/dissolve", headers=headers_b)
    assert dissolve.status_code in (200, 201), dissolve.text[:300]

    assert await _scoped_counts(sessionmaker) == before
    blocked = await client.post(
        f"/v1/workspaces/{ws.id}/copilot/threads/{shared_thread_id}/messages",
        json={"content": "Noch da?"},
        headers=headers_b,
    )
    assert blocked.status_code == 409
    assert await _scoped_counts(sessionmaker) == before


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_EXPECTED_COLUMNS = {
    "id",
    "report_job_id",
    "analysis_job_id",
    "chat_message_id",
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


async def test_schema_has_no_prompt_or_text_field_and_each_origin_cascades(db_engine) -> None:
    def introspect(sync_conn):
        insp = inspect(sync_conn)
        return insp.get_columns("llm_generations"), insp.get_foreign_keys("llm_generations")

    async with db_engine.connect() as conn:
        columns, fks = await conn.run_sync(introspect)

    assert {c["name"] for c in columns} == _EXPECTED_COLUMNS
    for column in columns:
        name, type_ = column["name"], str(column["type"]).upper()
        assert "TEXT" not in type_ and "JSON" not in type_, name
        assert not any(w in name for w in ("text", "content", "response", "answer", "body")), name
        assert not name.startswith("prompt") or name in {"prompt_hash", "prompt_tokens"}, name
    assert {fk["referred_table"]: fk["options"].get("ondelete") for fk in fks} == {
        "report_jobs": "CASCADE",
        "analysis_jobs": "CASCADE",
        "chat_messages": "CASCADE",
    }


async def test_single_ref_check_rejects_rows_with_two_origins(db_engine) -> None:
    insert = text(
        "INSERT INTO llm_generations (id, source, provider, model, status, attempt, prompt_hash,"
        " report_job_id, analysis_job_id) VALUES (gen_random_uuid(), 'analysis', 'p', 'm', 'ok',"
        " 1, 'h', gen_random_uuid(), gen_random_uuid())"
    )
    with pytest.raises(Exception, match="ck_llm_generations_single_ref"):
        async with db_engine.begin() as conn:
            await conn.execute(insert)
