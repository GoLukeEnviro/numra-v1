"""Alembic-Migration `llm_generations_usage_columns` auf wegwerfbaren Datenbanken
(nie die Anwendungs-DB): Up/Down/Up, Altzeilen-Uebernahme, ON DELETE-Regel."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy.engine import make_url

API_DIR = Path(__file__).resolve().parents[2]
PREV = "7c3e9a51b2d8"
BASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_test"
)
PREFIX = "llmgen_migration_"


@pytest.fixture
def migration_url():
    name = PREFIX + uuid.uuid4().hex
    admin_url = (
        make_url(BASE_URL).set(drivername="postgresql").render_as_string(hide_password=False)
    )

    async def create():
        conn = await asyncpg.connect(admin_url)
        try:
            await conn.execute(f'CREATE DATABASE "{name}"')
        finally:
            await conn.close()

    asyncio.run(create())
    yield make_url(BASE_URL).set(database=name).render_as_string(hide_password=False)

    async def cleanup():
        assert name.startswith(PREFIX)
        conn = await asyncpg.connect(admin_url)
        try:
            await conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        finally:
            await conn.close()

    asyncio.run(cleanup())


def _alembic(url: str, command: str, revision: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", command, revision],
        cwd=API_DIR,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr


def _sql(url: str, query: str, *args):
    async def run():
        conn = await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))
        try:
            return [dict(r) for r in await conn.fetch(query, *args)]
        finally:
            await conn.close()

    return asyncio.run(run())


def _columns(url: str) -> set[str]:
    rows = _sql(
        url,
        "SELECT column_name FROM information_schema.columns WHERE table_name='llm_generations'",
    )
    return {r["column_name"] for r in rows}


def _heads_after_prev() -> list[str]:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=API_DIR,
        capture_output=True,
        text=True,
        timeout=60,
    )
    return [line.split()[0] for line in result.stdout.splitlines() if line.strip()]


def test_up_down_up_and_legacy_row_is_adopted(migration_url) -> None:
    _alembic(migration_url, "upgrade", PREV)
    legacy_cols = _columns(migration_url)
    assert {"token_usage"} <= legacy_cols and "source" not in legacy_cols
    for status, tag in (("OK", "h1"), ("success", "h2"), ("failed", "h3"), ("Retry", "h4")):
        _sql(
            migration_url,
            "INSERT INTO llm_generations (id, provider, model, status, prompt_hash)"
            f" VALUES (gen_random_uuid(), 'ollama_cloud', 'm', '{status}', '{tag}')",
        )

    _alembic(migration_url, "upgrade", "head")
    up_cols = _columns(migration_url)
    assert {
        "source",
        "attempt",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    } <= up_cols
    assert "token_usage" not in up_cols
    rows = _sql(
        migration_url,
        "SELECT prompt_hash, source, status, attempt, prompt_tokens FROM llm_generations"
        " ORDER BY prompt_hash",
    )
    # Unbekannte Altwerte ('success'/'failed') duerfen den CHECK nie verletzen -> 'error'.
    assert [(r["prompt_hash"], r["status"]) for r in rows] == [
        ("h1", "ok"),
        ("h2", "error"),
        ("h3", "error"),
        ("h4", "retry"),
    ]
    assert {(r["source"], r["attempt"], r["prompt_tokens"]) for r in rows} == {("report", 1, None)}

    _alembic(migration_url, "downgrade", PREV)
    assert _columns(migration_url) == legacy_cols
    assert len(_sql(migration_url, "SELECT status FROM llm_generations")) == 4

    _alembic(migration_url, "upgrade", "head")
    assert _columns(migration_url) == up_cols


def test_report_job_fk_cascades_on_delete(migration_url) -> None:
    _alembic(migration_url, "upgrade", "head")
    (fk,) = _sql(
        migration_url,
        "SELECT confdeltype::text AS confdeltype FROM pg_constraint"
        " WHERE conrelid='llm_generations'::regclass"
        " AND contype='f' AND confrelid='report_jobs'::regclass",
    )
    assert fk["confdeltype"] == "c"


def test_check_constraints_exist_after_upgrade_and_not_after_downgrade(migration_url) -> None:
    def names() -> set[str]:
        rows = _sql(
            migration_url,
            "SELECT conname FROM pg_constraint WHERE conrelid='llm_generations'::regclass"
            " AND contype='c'",
        )
        return {r["conname"] for r in rows}

    _alembic(migration_url, "upgrade", "head")
    assert names() == {
        "ck_llm_generations_source",
        "ck_llm_generations_status",
        "ck_llm_generations_attempt",
        "ck_llm_generations_single_ref",
    }
    insert = (
        "INSERT INTO llm_generations (id, source, provider, model, status, attempt, prompt_hash)"
        " VALUES (gen_random_uuid(), '{}', 'p', 'm', '{}', {}, 'h')"
    )
    for source, status, attempt in (
        ("other", "ok", 1),
        ("report", "bogus", 1),
        ("report", "ok", 0),
    ):
        with pytest.raises(asyncpg.CheckViolationError):
            _sql(migration_url, insert.format(source, status, attempt))
    _alembic(migration_url, "downgrade", PREV)
    assert names() == set()


def test_single_new_head_on_top_of_previous_head() -> None:
    heads = _heads_after_prev()
    assert len(heads) == 1 and heads[0] != PREV


REFS = "c5a9d3e72b16"


def _fk_rules(url: str) -> dict[str, str]:
    rows = _sql(
        url,
        "SELECT confrelid::regclass::text AS parent, confdeltype::text AS rule"
        " FROM pg_constraint WHERE conrelid='llm_generations'::regclass AND contype='f'",
    )
    return {r["parent"]: r["rule"] for r in rows}


def _check_names(url: str) -> set[str]:
    rows = _sql(
        url,
        "SELECT conname FROM pg_constraint WHERE conrelid='llm_generations'::regclass"
        " AND contype='c'",
    )
    return {r["conname"] for r in rows}


def test_refs_up_down_up_keeps_legacy_rows_and_sets_cascade_rules(migration_url) -> None:
    _alembic(migration_url, "upgrade", "9d2f6b83a1c4")
    before_cols = _columns(migration_url)
    assert not {"analysis_job_id", "chat_message_id"} & before_cols
    before_checks = _check_names(migration_url)
    _sql(
        migration_url,
        "INSERT INTO llm_generations (id, source, provider, model, status, attempt, prompt_hash)"
        " VALUES (gen_random_uuid(), 'report', 'p', 'm', 'ok', 1, 'legacy')",
    )

    _alembic(migration_url, "upgrade", REFS)
    up_cols = _columns(migration_url)
    assert {"analysis_job_id", "chat_message_id"} <= up_cols
    assert _fk_rules(migration_url) == {
        "report_jobs": "c",
        "analysis_jobs": "c",
        "chat_messages": "c",
    }
    assert _check_names(migration_url) == before_checks | {"ck_llm_generations_single_ref"}
    (legacy,) = _sql(
        migration_url,
        "SELECT report_job_id, analysis_job_id, chat_message_id FROM llm_generations",
    )
    assert set(legacy.values()) == {None}

    _alembic(migration_url, "downgrade", "9d2f6b83a1c4")
    assert _columns(migration_url) == before_cols
    assert _check_names(migration_url) == before_checks
    assert _fk_rules(migration_url) == {"report_jobs": "c"}
    assert len(_sql(migration_url, "SELECT 1 FROM llm_generations")) == 1

    _alembic(migration_url, "upgrade", REFS)
    assert _columns(migration_url) == up_cols


def test_single_ref_check_rejects_two_origins_after_upgrade(migration_url) -> None:
    _alembic(migration_url, "upgrade", "head")
    with pytest.raises(asyncpg.CheckViolationError):
        _sql(
            migration_url,
            "INSERT INTO llm_generations (id, source, provider, model, status, attempt,"
            " prompt_hash, analysis_job_id, chat_message_id) VALUES (gen_random_uuid(),"
            " 'copilot', 'p', 'm', 'ok', 1, 'h', gen_random_uuid(), gen_random_uuid())",
        )


def test_refs_revision_sits_on_top_of_the_report_revision_in_a_single_head_chain() -> None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    script = ScriptDirectory.from_config(config)
    heads = script.get_heads()
    assert len(heads) == 1
    assert REFS in {rev.revision for rev in script.walk_revisions(head=heads[0])}
    assert script.get_revision(REFS).down_revision == "9d2f6b83a1c4"


def test_refs_foreign_keys_are_validated_after_upgrade(migration_url) -> None:
    _alembic(migration_url, "upgrade", REFS)
    rows = _sql(
        migration_url,
        "SELECT convalidated FROM pg_constraint"
        " WHERE conrelid='llm_generations'::regclass AND contype='f'",
    )
    assert len(rows) == 3 and all(r["convalidated"] for r in rows)


def test_refs_upgrade_fails_fast_on_lock_conflict_and_can_be_repeated(migration_url) -> None:
    """Haelt ein anderer Prozess die Tabelle gesperrt, bricht die Migration per
    `lock_timeout` kontrolliert ab (nichts halb angewendet) und laeuft danach durch."""
    _alembic(migration_url, "upgrade", "9d2f6b83a1c4")
    plain_url = migration_url.replace("postgresql+asyncpg://", "postgresql://")

    async def blocked_attempt() -> subprocess.CompletedProcess[str]:
        conn = await asyncpg.connect(plain_url)
        tx = conn.transaction()
        await tx.start()
        try:
            await conn.execute("LOCK TABLE llm_generations IN ACCESS EXCLUSIVE MODE")
            return await asyncio.to_thread(
                subprocess.run,
                [sys.executable, "-m", "alembic", "upgrade", REFS],
                cwd=API_DIR,
                env={**os.environ, "DATABASE_URL": migration_url},
                capture_output=True,
                text=True,
                timeout=120,
            )
        finally:
            await tx.rollback()
            await conn.close()

    result = asyncio.run(blocked_attempt())
    assert result.returncode != 0
    assert "lock timeout" in result.stderr
    assert not {"analysis_job_id", "chat_message_id"} & _columns(migration_url)

    _alembic(migration_url, "upgrade", REFS)
    assert {"analysis_job_id", "chat_message_id"} <= _columns(migration_url)
