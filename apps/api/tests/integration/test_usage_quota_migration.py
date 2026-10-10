"""Migration `e5b7d1a9c3f2` (usage_reservations) auf einer wegwerfbaren Datenbank:
genau ein Head, rein additiv (keine bestehende Tabelle veraendert), wiederholbar."""

from __future__ import annotations

import subprocess
import sys

from test_llm_generations_migration import (
    API_DIR,
    _alembic,
    _sql,
    migration_url,  # noqa: F401  (Fixture)
)

PREV = "d2a8c4f6b1e3"
REV = "e5b7d1a9c3f2"


def _tables(url: str) -> set[str]:
    rows = _sql(url, "SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
    return {r["table_name"] for r in rows}


def test_single_head_on_top_of_previous() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=API_DIR,
        capture_output=True,
        text=True,
        timeout=60,
    )
    heads = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(heads) == 1 and heads[0].startswith(REV)


def test_upgrade_only_adds_the_ledger_table(migration_url) -> None:  # noqa: F811
    _alembic(migration_url, "upgrade", PREV)
    before = _tables(migration_url)

    _alembic(migration_url, "upgrade", REV)

    assert _tables(migration_url) - before == {"usage_reservations"}
    assert before <= _tables(migration_url)
    columns = {
        r["column_name"]: r["is_nullable"]
        for r in _sql(
            migration_url,
            "SELECT column_name, is_nullable FROM information_schema.columns"
            " WHERE table_name='usage_reservations'",
        )
    }
    assert set(columns) == {
        "id",
        "user_id",
        "feature",
        "ref_id",
        "state",
        "created_at",
        "finished_at",
    }
    assert columns["finished_at"] == "YES"
    assert _sql(migration_url, "SELECT count(*) AS n FROM usage_reservations") == [{"n": 0}]


def test_downgrade_and_reupgrade_are_repeatable(migration_url) -> None:  # noqa: F811
    _alembic(migration_url, "upgrade", REV)
    _alembic(migration_url, "downgrade", PREV)
    assert "usage_reservations" not in _tables(migration_url)
    _alembic(migration_url, "upgrade", REV)
    assert "usage_reservations" in _tables(migration_url)
