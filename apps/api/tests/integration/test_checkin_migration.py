"""Actual Alembic upgrades on unique disposable databases, never the application DB."""

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

from numra_api.db import build_engine, build_sessionmaker
from numra_api.services.checkin_service import get_checkin, submit_checkin

API_DIR = Path(__file__).resolve().parents[2]
OLD = "d4e5f6a7b8c9"
NEW = "e6a1b2c3d4e5"
BASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://numra:numra_dev_password@127.0.0.1:5432/numra_test"
)


@pytest.fixture
def migration_url():
    name = "web06a_migration_" + uuid.uuid4().hex
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
        assert name.startswith("web06a_migration_") and len(name) == 49
        conn = await asyncpg.connect(admin_url)
        try:
            await conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        finally:
            await conn.close()

    asyncio.run(cleanup())


def _alembic(url, command, revision, success=True):
    result = subprocess.run(
        [sys.executable, "-m", "alembic", command, revision],
        cwd=API_DIR,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
        timeout=90,
    )
    if success:
        assert result.returncode == 0, result.stderr
    else:
        assert result.returncode != 0
    return result.stderr


async def _connect_db(url):
    return await asyncpg.connect(url.replace("postgresql+asyncpg://", "postgresql://"))


async def _seed(url, case):
    conn = await _connect_db(url)
    try:
        a, b, connection, workspace, template, round_id, d1, d2 = [uuid.uuid4() for _ in range(8)]
        for user in [a, b]:
            await conn.execute(
                "INSERT INTO users(id,email,password_hash,role,is_active) "
                "VALUES($1,$2,'synthetic','USER',true)",
                user,
                f"{user}@example.com",
            )
        await conn.execute(
            "INSERT INTO user_connections(id,user_a_id,user_b_id) VALUES($1,$2,$3)",
            connection,
            a,
            b,
        )
        await conn.execute(
            "INSERT INTO relationship_workspaces(id,connection_id) VALUES($1,$2)",
            workspace,
            connection,
        )
        for user in [a, b]:
            await conn.execute(
                "INSERT INTO workspace_members(id,workspace_id,user_id) VALUES($1,$2,$3)",
                uuid.uuid4(),
                workspace,
                user,
            )
        await conn.execute(
            "INSERT INTO checkin_templates(id,workspace_id,version) VALUES($1,$2,1)",
            template,
            workspace,
        )
        for d, key in [(d1, "closeness"), (d2, "sexual_connection")]:
            await conn.execute(
                "INSERT INTO checkin_dimensions(id,workspace_id,template_version,"
                "semantic_key,label,description) VALUES($1,$2,1,$3,$3,$4)",
                d,
                workspace,
                key,
                "original synthetic description",
            )
        status = "ANALYZED" if case == "analyzed" else "AWAITING_SUBMISSIONS"
        await conn.execute(
            "INSERT INTO relationship_checkins(id,workspace_id,checkin_template_version,"
            "status) VALUES($1,$2,1,$3)",
            round_id,
            workspace,
            status,
        )
        users = [a, b] if case in ["analyzed", "two_submitters"] else [a]
        if case == "unsubmitted":
            users = []
        for user in users:
            for d, key in [(d1, "closeness"), (d2, "sexual_connection")]:
                if case == "partial" and d == d2:
                    continue
                await conn.execute(
                    "INSERT INTO checkin_responses(id,checkin_id,user_id,dimension_id,"
                    "semantic_key,value) VALUES($1,$2,$3,$4,$5,7)",
                    uuid.uuid4(),
                    round_id,
                    user,
                    d,
                    "wrong_key" if case == "key_mismatch" else key,
                )
        if case == "analyzed":
            await conn.execute(
                "INSERT INTO checkin_analyses(id,checkin_id,workspace_id,"
                "checkin_template_version,result_json) VALUES($1,$2,$3,1,$4::jsonb)",
                uuid.uuid4(),
                round_id,
                workspace,
                '{"closeness":{"absolute_gap":0,"direction":"NO_PRIOR_DATA","rolling_trend":0,'
                '"sample_size":1,"historical_delta":null,"sufficient_evidence":false}}',
            )
        if case == "retired":
            await conn.execute("UPDATE checkin_dimensions SET active=false WHERE id=$1", d2)
        if case == "range_changed":
            await conn.execute("UPDATE checkin_dimensions SET scale_max=6 WHERE id=$1", d2)
        if case == "label_changed":
            await conn.execute(
                "UPDATE checkin_dimensions SET label='migration-time label', "
                "description='migration-time description' WHERE id=$1",
                d2,
            )
        original = await _retained(conn)
        return workspace, a, b, round_id, d1, d2, original
    finally:
        await conn.close()


async def _retained(conn):
    return {
        table: [dict(r) for r in await conn.fetch(f"SELECT * FROM {table} ORDER BY id")]
        for table in ["checkin_responses", "checkin_analyses"]
    }


def test_empty_upgrade_and_safe_downgrade(migration_url):
    _alembic(migration_url, "upgrade", "head")
    _alembic(migration_url, "downgrade", OLD)
    _alembic(migration_url, "upgrade", "head")


@pytest.mark.parametrize(
    "case",
    [
        "analyzed",
        "compatible",
        "unsubmitted",
        "label_changed",
        "partial",
        "retired",
        "range_changed",
        "key_mismatch",
        "two_submitters",
    ],
)
def test_legacy_migration_and_atomic_rejection(migration_url, case):
    _alembic(migration_url, "upgrade", OLD)
    workspace, a, b, round_id, d1, d2, original = asyncio.run(_seed(migration_url, case))
    compatible = case in ["analyzed", "compatible", "unsubmitted", "label_changed"]
    log = _alembic(migration_url, "upgrade", "head", success=compatible)

    async def inspect():
        conn = await _connect_db(migration_url)
        try:
            assert await _retained(conn) == original
            version = await conn.fetchval("SELECT version_num FROM alembic_version")
            assert version == (NEW if compatible else OLD)
            if not compatible:
                assert "CHECKIN_MIGRATION_INCOMPATIBLE" in log
                assert await conn.fetchval("SELECT to_regclass('checkin_round_dimensions')") is None
                assert not await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
                    "WHERE table_name='relationship_checkins' AND column_name='snapshot_origin')"
                )
                return
            origin = await conn.fetchval(
                "SELECT snapshot_origin FROM relationship_checkins WHERE id=$1", round_id
            )
            assert origin == ("LEGACY_MISSING" if case == "analyzed" else "MIGRATION_CURRENT")
            dims = await conn.fetch(
                "SELECT * FROM checkin_round_dimensions WHERE checkin_id=$1", round_id
            )
            assert len(dims) == (0 if case == "analyzed" else 2)
            assert (
                await conn.fetchval(
                    "SELECT dimension_class FROM checkin_dimensions WHERE id=$1", d2
                )
                == "INTIMATE"
            )
            if case == "label_changed":
                changed = next(d for d in dims if d["dimension_id"] == d2)
                assert changed["label"] == "migration-time label"
            with pytest.raises(asyncpg.ForeignKeyViolationError):
                await conn.execute("DELETE FROM checkin_dimensions WHERE id=$1", d1)
            with pytest.raises(asyncpg.RaiseError, match="CHECKIN_DIMENSION_IDENTITY_IMMUTABLE"):
                await conn.execute(
                    "UPDATE checkin_dimensions SET semantic_key='redefined' WHERE id=$1", d1
                )
            if dims:
                with pytest.raises(asyncpg.RaiseError, match="CHECKIN_SNAPSHOT_IMMUTABLE"):
                    await conn.execute(
                        "UPDATE checkin_round_dimensions SET label='changed' WHERE checkin_id=$1",
                        round_id,
                    )
            if dims:
                with pytest.raises(asyncpg.RaiseError, match="CHECKIN_SNAPSHOT_IMMUTABLE"):
                    await conn.execute(
                        "DELETE FROM checkin_round_dimensions WHERE checkin_id=$1", round_id
                    )
            assert await _retained(conn) == original
        finally:
            await conn.close()

    asyncio.run(inspect())
    if compatible:

        async def verify_service():
            engine = build_engine(migration_url)
            try:
                async with build_sessionmaker(engine)() as db:
                    result = await get_checkin(
                        db, workspace_id=workspace, user_id=a, checkin_id=round_id
                    )
                    assert result.checkin.snapshot_origin == (
                        "LEGACY_MISSING" if case == "analyzed" else "MIGRATION_CURRENT"
                    )
                    if case in ["compatible", "label_changed"]:
                        completed = await submit_checkin(
                            db,
                            workspace_id=workspace,
                            user_id=b,
                            round_id=round_id,
                            idempotency_key="complete-migrated",
                            responses=[(d1, 3), (d2, 4)],
                        )
                        assert completed.checkin.status == "ANALYZED"
                        assert len(completed.analysis.result_json) == 2
                        await db.commit()
            finally:
                await engine.dispose()

        asyncio.run(verify_service())
        if case != "analyzed":
            log = _alembic(migration_url, "downgrade", OLD, success=False)
            assert "CHECKIN_DOWNGRADE_UNSAFE" in log

        async def verify_parent_cascade():
            conn = await _connect_db(migration_url)
            try:
                await conn.execute("DELETE FROM relationship_workspaces WHERE id=$1", workspace)
                assert await conn.fetchval("SELECT count(*) FROM checkin_round_dimensions") == 0
                assert await conn.fetchval("SELECT count(*) FROM checkin_responses") == 0
            finally:
                await conn.close()

        asyncio.run(verify_parent_cascade())
