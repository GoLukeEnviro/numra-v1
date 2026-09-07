"""Migration-Backfill-Property-Test fuer a1b2c3d4e5f7 (person_account_mode Backfill +
uq_people_user_id_self_mode). Faehrt die ECHTE Alembic-Migration per Subprocess gegen
eine eigene, isolierte Postgres-Schema-Instanz -- kein `Base.metadata.create_all`
(das conftest.py `db_engine`-Fixture umgeht Alembic komplett und ist hier bewusst
nicht involviert). Property: nach dem Upgrade hat jede `user_id` in `people` GENAU
eine SELF-Zeile -- unabhaengig davon, ob sie 0, 1 oder N Person-Zeilen hatte.
"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

import asyncpg
import pytest

API_DIR = Path(__file__).resolve().parents[2]
MIGRATION_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_test",
)
ASYNCPG_URL = MIGRATION_DB_URL.replace("postgresql+asyncpg://", "postgresql://")
PREVIOUS_HEAD = "b32b8d41f01b"
THIS_REVISION = "a1b2c3d4e5f7"


def _run_alembic(*args: str) -> None:
    result = subprocess.run(
        ["uv", "run", "alembic", *args],
        cwd=str(API_DIR),
        env={**os.environ, "DATABASE_URL": MIGRATION_DB_URL},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"alembic {' '.join(args)} failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


async def _reset_schema() -> None:
    conn = await asyncpg.connect(ASYNCPG_URL)
    try:
        await conn.execute("DROP SCHEMA public CASCADE")
        await conn.execute("CREATE SCHEMA public")
    finally:
        await conn.close()


async def _insert_user(conn: asyncpg.Connection) -> uuid.UUID:
    user_id = uuid.uuid4()
    await conn.execute(
        "INSERT INTO users (id, email, password_hash, role, is_active, created_at) "
        "VALUES ($1, $2, 'x', 'USER', true, now())",
        user_id,
        f"{user_id}@example.test",
    )
    return user_id


async def _insert_person(
    conn: asyncpg.Connection, *, user_id: uuid.UUID, created_at_offset_seconds: int
) -> uuid.UUID:
    person_id = uuid.uuid4()
    await conn.execute(
        "INSERT INTO people (id, user_id, birth_first_names, birth_last_name, birth_date, "
        "created_at, updated_at) "
        "VALUES ($1, $2, 'Test', 'Person', '1990-01-01', "
        "now() - ($3 * interval '1 second'), now())",
        person_id,
        user_id,
        created_at_offset_seconds,
    )
    return person_id


@pytest.mark.integration
def test_person_account_mode_backfill_property_and_roundtrip() -> None:
    import asyncio

    asyncio.run(_reset_schema())
    try:
        # Schema bis zum vorherigen Head aufbauen -- die people-Tabelle existiert dann
        # noch OHNE person_account_mode-Spalte, wie vor dieser Migration.
        _run_alembic("upgrade", PREVIOUS_HEAD)

        async def seed() -> dict[str, list[uuid.UUID]]:
            conn = await asyncpg.connect(ASYNCPG_URL)
            try:
                await _insert_user(conn)  # 0 Person-Zeilen

                user_one = await _insert_user(conn)  # 1 Person-Zeile
                person_one = await _insert_person(
                    conn, user_id=user_one, created_at_offset_seconds=0
                )

                user_many = await _insert_user(conn)  # 3 Person-Zeilen, aelteste zuerst
                oldest = await _insert_person(
                    conn, user_id=user_many, created_at_offset_seconds=300
                )
                middle = await _insert_person(
                    conn, user_id=user_many, created_at_offset_seconds=150
                )
                newest = await _insert_person(conn, user_id=user_many, created_at_offset_seconds=0)
                return {
                    "user_zero": [],
                    "user_one": [person_one],
                    "user_many_oldest_first": [oldest, middle, newest],
                }
            finally:
                await conn.close()

        seeded = asyncio.run(seed())

        async def assert_backfill() -> None:
            conn = await asyncpg.connect(ASYNCPG_URL)
            try:
                # Property: pro user_id genau eine SELF-Zeile.
                rows = await conn.fetch(
                    "SELECT user_id, "
                    "count(*) FILTER (WHERE person_account_mode = 'SELF') AS self_count "
                    "FROM people GROUP BY user_id"
                )
                assert rows, "expected seeded people rows after backfill"
                for row in rows:
                    assert row["self_count"] == 1, (
                        f"user_id={row['user_id']} has {row['self_count']} SELF rows, "
                        "expected exactly 1"
                    )

                # Konkret: die aelteste Person-Zeile des Multi-Person-Users ist SELF, die
                # anderen beiden MANAGED_OTHER.
                oldest_id = seeded["user_many_oldest_first"][0]
                middle_id = seeded["user_many_oldest_first"][1]
                newest_id = seeded["user_many_oldest_first"][2]
                oldest_mode = await conn.fetchval(
                    "SELECT person_account_mode FROM people WHERE id = $1", oldest_id
                )
                middle_mode = await conn.fetchval(
                    "SELECT person_account_mode FROM people WHERE id = $1", middle_id
                )
                newest_mode = await conn.fetchval(
                    "SELECT person_account_mode FROM people WHERE id = $1", newest_id
                )
                assert oldest_mode == "SELF"
                assert middle_mode == "MANAGED_OTHER"
                assert newest_mode == "MANAGED_OTHER"

                # Der Ein-Person-User ist SELF.
                single_mode = await conn.fetchval(
                    "SELECT person_account_mode FROM people WHERE id = $1",
                    seeded["user_one"][0],
                )
                assert single_mode == "SELF"

                # Der Partial-Unique-Index existiert und ist tatsaechlich unique+partial.
                index_row = await conn.fetchrow(
                    "SELECT indexdef FROM pg_indexes "
                    "WHERE indexname = 'uq_people_user_id_self_mode'"
                )
                assert index_row is not None
                assert "UNIQUE" in index_row["indexdef"]
                assert "person_account_mode" in index_row["indexdef"]
            finally:
                await conn.close()

        # 1) Upgrade auf diese Migration -> Backfill-Property pruefen.
        _run_alembic("upgrade", THIS_REVISION)
        asyncio.run(assert_backfill())

        # 2) Downgrade -> Spalte und Index wieder weg.
        _run_alembic("downgrade", PREVIOUS_HEAD)

        async def assert_downgraded() -> None:
            conn = await asyncpg.connect(ASYNCPG_URL)
            try:
                col = await conn.fetchval(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name = 'people' AND column_name = 'person_account_mode'"
                )
                assert col == 0
                idx = await conn.fetchval(
                    "SELECT count(*) FROM pg_indexes "
                    "WHERE indexname = 'uq_people_user_id_self_mode'"
                )
                assert idx == 0
                # Die urspruenglichen People-Zeilen ueberleben den Downgrade unangetastet.
                count = await conn.fetchval("SELECT count(*) FROM people")
                assert count == 4
            finally:
                await conn.close()

        asyncio.run(assert_downgraded())

        # 3) Upgrade erneut (Roundtrip) -> Backfill-Property haelt weiterhin.
        _run_alembic("upgrade", THIS_REVISION)
        asyncio.run(assert_backfill())
    finally:
        asyncio.run(_reset_schema())
