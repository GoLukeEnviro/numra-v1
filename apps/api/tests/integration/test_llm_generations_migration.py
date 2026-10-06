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
        " AND contype='f'",
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
