"""Alembic-Migration `feature_flag_bootstrap` auf wegwerfbaren Datenbanken (nie die
Anwendungs-DB). Bestandsupgrade => `adopted`, Flagwerte + updated_at bitgleich."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy.engine import make_url

API_DIR = Path(__file__).resolve().parents[2]
PREV = "04d4d6f4c5a0"  # feature_flags-Tabelle + Seed (wird nicht umgeschrieben)
BASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_test"
)
PREFIX = "flagboot_migration_"


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
        timeout=90,
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


def _flag_rows(url: str):
    return _sql(url, "SELECT * FROM feature_flags ORDER BY name")


def test_existing_flags_are_adopted_bit_identical(migration_url) -> None:
    _alembic(migration_url, "upgrade", PREV)
    # Admin hat zur Laufzeit Werte/Zeitstempel veraendert -- sie muessen unberuehrt bleiben.
    _sql(
        migration_url,
        "UPDATE feature_flags SET enabled = NOT enabled, updated_at = $1 WHERE name IN "
        "('checkins','copilot')",
        datetime(2026, 10, 5, 12, 34, 56, 789012, tzinfo=UTC),
    )
    before = _flag_rows(migration_url)
    assert len(before) == 7

    _alembic(migration_url, "upgrade", "head")

    assert _flag_rows(migration_url) == before
    rows = _sql(
        migration_url, "SELECT id, profile, source, initialized_at FROM feature_flag_bootstrap"
    )
    assert len(rows) == 1
    assert (rows[0]["id"], rows[0]["profile"], rows[0]["source"]) == (1, "pre-existing", "adopted")
    assert rows[0]["initialized_at"] is not None


def test_empty_flags_table_gets_no_status(migration_url) -> None:
    _alembic(migration_url, "upgrade", PREV)
    _sql(migration_url, "DELETE FROM feature_flags")
    _alembic(migration_url, "upgrade", "head")
    assert _sql(migration_url, "SELECT * FROM feature_flag_bootstrap") == []


def test_up_down_up_keeps_flags_and_readopts(migration_url) -> None:
    _alembic(migration_url, "upgrade", "head")
    before = _flag_rows(migration_url)

    _alembic(migration_url, "downgrade", PREV)
    assert _sql(migration_url, "SELECT to_regclass('feature_flag_bootstrap') AS t")[0]["t"] is None
    assert _flag_rows(migration_url) == before

    _alembic(migration_url, "upgrade", "head")
    rows = _sql(migration_url, "SELECT profile, source FROM feature_flag_bootstrap")
    assert rows == [{"profile": "pre-existing", "source": "adopted"}]
    assert _flag_rows(migration_url) == before
