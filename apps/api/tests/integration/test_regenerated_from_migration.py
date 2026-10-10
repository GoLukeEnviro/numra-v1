"""Migration `f8d3b6a1c4e9` (regenerated_from_id) auf einer wegwerfbaren Datenbank:
genau ein Head auf e5b7d1a9c3f2, rein additiv (zwei nullbare Spalten, zwei partielle
Unique-Indizes), Altzeilen bleiben unveraendert."""

from __future__ import annotations

import subprocess
import sys

from test_llm_generations_migration import (
    API_DIR,
    _alembic,
    _sql,
    migration_url,  # noqa: F401  (Fixture)
)

PREV = "e5b7d1a9c3f2"
REV = "f8d3b6a1c4e9"
TABLES = ("reports", "relationship_analyses")


def _columns(url: str, table: str) -> dict[str, str]:
    rows = _sql(
        url,
        "SELECT column_name, is_nullable FROM information_schema.columns"
        f" WHERE table_name='{table}'",
    )
    return {r["column_name"]: r["is_nullable"] for r in rows}


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
    show = subprocess.run(
        [sys.executable, "-m", "alembic", "show", REV],
        cwd=API_DIR,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert f"Parent: {PREV}" in show.stdout


def test_upgrade_only_adds_nullable_columns_and_partial_indexes(migration_url) -> None:  # noqa: F811
    _alembic(migration_url, "upgrade", PREV)
    before = {t: _columns(migration_url, t) for t in TABLES}

    _alembic(migration_url, "upgrade", REV)

    for table in TABLES:
        after = _columns(migration_url, table)
        assert set(after) - set(before[table]) == {"regenerated_from_id"}
        assert after["regenerated_from_id"] == "YES"
        assert set(before[table]) <= set(after)
    indexes = {
        r["indexname"]: r["indexdef"]
        for r in _sql(
            migration_url,
            "SELECT indexname, indexdef FROM pg_indexes"
            " WHERE indexname LIKE 'uq_%_live_regeneration'",
        )
    }
    assert set(indexes) == {
        "uq_reports_live_regeneration",
        "uq_relationship_analyses_live_regeneration",
    }
    assert all("UNIQUE" in d and "WHERE" in d for d in indexes.values())


def test_upgrade_is_repeatable_from_the_previous_revision(migration_url) -> None:  # noqa: F811
    _alembic(migration_url, "upgrade", REV)
    _alembic(migration_url, "downgrade", PREV)
    _alembic(migration_url, "upgrade", REV)

    assert "regenerated_from_id" in _columns(migration_url, "reports")
