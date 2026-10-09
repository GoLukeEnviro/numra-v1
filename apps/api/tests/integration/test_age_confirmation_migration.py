"""Migration `d2a8c4f6b1e3` (users.age_*) auf einer wegwerfbaren Datenbank (nie die
Anwendungs-DB): Spalten echt per information_schema geprueft, Bestandszeile bleibt NULL,
alter Code (INSERT ohne die neuen Spalten) funktioniert weiter."""

from __future__ import annotations

import subprocess
import sys

from test_llm_generations_migration import (
    API_DIR,
    _alembic,
    _sql,
    migration_url,  # noqa: F401  (Fixture)
)

PREV = "c5a9d3e72b16"
REV = "d2a8c4f6b1e3"


def _age_columns(url: str) -> dict[str, dict]:
    rows = _sql(
        url,
        "SELECT column_name, data_type, is_nullable, column_default, character_maximum_length"
        " FROM information_schema.columns"
        " WHERE table_name='users' AND column_name LIKE 'age_%'",
    )
    return {r["column_name"]: r for r in rows}


def _insert_user(url: str, email: str) -> None:
    _sql(
        url,
        "INSERT INTO users (id, email, password_hash, role, is_active)"
        f" VALUES (gen_random_uuid(), '{email}', 'x', 'USER', true)",
    )


def test_revision_is_a_single_head_chain_on_top_of_previous() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "heads"],
        cwd=API_DIR,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert len([line for line in result.stdout.splitlines() if line.strip()]) == 1


def test_upgrade_adds_nullable_columns_and_keeps_legacy_rows_unconfirmed(migration_url) -> None:  # noqa: F811
    _alembic(migration_url, "upgrade", PREV)
    assert _age_columns(migration_url) == {}
    _insert_user(migration_url, "legacy@example.com")

    _alembic(migration_url, "upgrade", REV)

    columns = _age_columns(migration_url)
    assert set(columns) == {"age_confirmed_at", "age_declaration_version"}
    assert columns["age_confirmed_at"]["data_type"] == "timestamp with time zone"
    assert columns["age_declaration_version"]["character_maximum_length"] == 40
    assert all(c["is_nullable"] == "YES" and c["column_default"] is None for c in columns.values())
    row = _sql(migration_url, "SELECT age_confirmed_at, age_declaration_version FROM users")
    assert row == [{"age_confirmed_at": None, "age_declaration_version": None}]
    _insert_user(migration_url, "old-code@example.com")
    assert _sql(
        migration_url, "SELECT count(*) AS n FROM users WHERE age_confirmed_at IS NULL"
    ) == [{"n": 2}]


def test_downgrade_and_reupgrade_are_repeatable(migration_url) -> None:  # noqa: F811
    _alembic(migration_url, "upgrade", REV)
    _alembic(migration_url, "downgrade", PREV)
    assert _age_columns(migration_url) == {}
    _alembic(migration_url, "upgrade", REV)
    assert set(_age_columns(migration_url)) == {"age_confirmed_at", "age_declaration_version"}
