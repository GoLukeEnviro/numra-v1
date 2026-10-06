"""Flag-Bootstrap (Plan v4 Variante A): einmaliges, statusgesteuertes Setzen der
Feature-Flags ueber `flags init --profile`. Laeuft gegen die Test-DB-Fixtures."""

from __future__ import annotations

import asyncio
import logging

import pytest
from sqlalchemy import delete, func, select, text

from numra_api.auth.passwords import hash_password
from numra_api.cli import init_flags
from numra_api.config import Settings
from numra_api.feature_flag_profiles import PROFILES
from numra_api.models import AdminAuditEvent, FeatureFlag, FeatureFlagBootstrap
from numra_api.models.enums import AuditAction
from numra_api.repositories.users import create_user
from numra_api.services.feature_flag_bootstrap import bootstrap_flags

pytestmark = pytest.mark.integration

ALL_FLAGS = {
    "v2_master",
    "connections",
    "relationship_workspaces",
    "checkins",
    "tasks",
    "copilot",
    "evidence_layer",
}
BETA_ON = {"v2_master", "connections", "relationship_workspaces", "copilot"}


@pytest.fixture(autouse=True)
async def _fresh_flag_state(sessionmaker):
    """conftest seedet 7x True ohne Bootstrap-Status. Diese Tests starten wie eine
    frische DB: keine Flag-Zeilen, kein Status, keine Audit-Events."""
    async with sessionmaker() as db:
        await db.execute(delete(FeatureFlag))
        await db.execute(delete(FeatureFlagBootstrap))
        await db.execute(delete(AdminAuditEvent))
        await db.commit()


async def _flags(sessionmaker) -> dict[str, bool]:
    async with sessionmaker() as db:
        rows = (await db.execute(select(FeatureFlag))).scalars().all()
        return {r.name: r.enabled for r in rows}


async def _status(sessionmaker) -> FeatureFlagBootstrap | None:
    async with sessionmaker() as db:
        return (await db.execute(select(FeatureFlagBootstrap))).scalar_one_or_none()


async def _audits(sessionmaker) -> list[AdminAuditEvent]:
    async with sessionmaker() as db:
        stmt = select(AdminAuditEvent).where(
            AdminAuditEvent.action == str(AuditAction.FEATURE_FLAG_CHANGED)
        )
        return list((await db.execute(stmt)).scalars().all())


async def _run(sessionmaker, profile: str, dry_run: bool = False):
    async with sessionmaker() as db:
        return await bootstrap_flags(db, profile=profile, dry_run=dry_run)


def test_profiles_are_versioned_and_complete() -> None:
    assert set(PROFILES) == {"all-off", "beta", "audit-all-on"}
    for values in PROFILES.values():
        assert set(values) == ALL_FLAGS
    assert {k for k, v in PROFILES["beta"].items() if v} == BETA_ON
    assert not any(PROFILES["all-off"].values())
    assert all(PROFILES["audit-all-on"].values())


async def test_fresh_db_all_off_sets_seven_flags_off(sessionmaker) -> None:
    result = await _run(sessionmaker, "all-off")
    assert result.applied is True
    assert await _flags(sessionmaker) == dict.fromkeys(ALL_FLAGS, False)
    status = await _status(sessionmaker)
    assert status is not None
    assert (status.profile, status.source) == ("all-off", "bootstrap")
    assert status.initialized_at is not None


async def test_fresh_db_audit_all_on_sets_seven_flags_on(sessionmaker) -> None:
    await _run(sessionmaker, "audit-all-on")
    assert await _flags(sessionmaker) == dict.fromkeys(ALL_FLAGS, True)


async def test_beta_profile_sets_four_on(sessionmaker) -> None:
    await _run(sessionmaker, "beta")
    flags = await _flags(sessionmaker)
    assert {k for k, v in flags.items() if v} == BETA_ON
    assert len(flags) == 7


async def test_unknown_profile_is_rejected_without_writes(sessionmaker) -> None:
    with pytest.raises(ValueError, match="unknown profile"):
        await _run(sessionmaker, "nope")
    assert await _status(sessionmaker) is None
    assert await _flags(sessionmaker) == {}


async def test_repeat_is_noop(sessionmaker) -> None:
    await _run(sessionmaker, "beta")
    audits_before = len(await _audits(sessionmaker))
    result = await _run(sessionmaker, "beta")
    assert result.applied is False
    assert len(await _audits(sessionmaker)) == audits_before


async def test_profile_switch_after_init_is_noop_with_hint(sessionmaker, caplog) -> None:
    await _run(sessionmaker, "beta")
    before = await _flags(sessionmaker)
    with caplog.at_level(logging.WARNING):
        result = await _run(sessionmaker, "audit-all-on")
    assert result.applied is False
    assert await _flags(sessionmaker) == before
    status = await _status(sessionmaker)
    assert status is not None and status.profile == "beta"
    assert "beta" in caplog.text and "audit-all-on" in caplog.text


async def test_existing_status_never_overwrites_admin_changes(sessionmaker) -> None:
    """Gelooeschter urspruenglicher Admin => updated_by_user_id IS NULL (FK SET NULL).
    Das ist KEIN Kriterium: nur der Status entscheidet, Init ueberschreibt nichts."""
    async with sessionmaker() as db:
        admin = await create_user(
            db, email="gone-admin@example.com", password_hash=hash_password("x" * 14)
        )
        await db.commit()
        admin_id = admin.id
    await _run(sessionmaker, "all-off")
    async with sessionmaker() as db:
        flag = await db.get(FeatureFlag, "copilot")
        assert flag is not None
        flag.enabled = True
        flag.updated_by_user_id = admin_id
        await db.commit()
    async with sessionmaker() as db:
        await db.execute(text("DELETE FROM users WHERE id = :i"), {"i": admin_id})
        await db.commit()
    async with sessionmaker() as db:
        flag = await db.get(FeatureFlag, "copilot")
        assert flag is not None and flag.updated_by_user_id is None and flag.enabled is True

    result = await _run(sessionmaker, "all-off")
    assert result.applied is False
    assert (await _flags(sessionmaker))["copilot"] is True


async def test_bootstrap_audit_entries_have_null_actor_and_origin(sessionmaker) -> None:
    await _run(sessionmaker, "beta")
    audits = await _audits(sessionmaker)
    assert len(audits) == 7  # frische DB: jede Zeile neu angelegt
    for event in audits:
        assert event.actor_user_id is None
        assert event.safe_metadata["origin"] == "bootstrap"
        assert event.safe_metadata["profile"] == "beta"
    by_flag = {e.safe_metadata["flag"]: e.safe_metadata for e in audits}
    assert by_flag["copilot"]["to"] is True and by_flag["copilot"]["from"] is None
    assert by_flag["tasks"]["to"] is False


async def test_bootstrap_only_audits_actual_changes(sessionmaker) -> None:
    async with sessionmaker() as db:
        for name in ALL_FLAGS:
            db.add(FeatureFlag(name=name, enabled=False))
        await db.commit()
    await _run(sessionmaker, "beta")
    audits = await _audits(sessionmaker)
    assert {e.safe_metadata["flag"] for e in audits} == BETA_ON
    assert all(e.safe_metadata["from"] is False for e in audits)


async def test_dry_run_writes_nothing_and_reports_diff(sessionmaker) -> None:
    result = await _run(sessionmaker, "beta", dry_run=True)
    assert result.applied is False
    assert {c.name for c in result.changes if c.after} == BETA_ON
    assert await _status(sessionmaker) is None
    assert await _flags(sessionmaker) == {}
    assert await _audits(sessionmaker) == []


async def test_dry_run_with_existing_status_reports_noop(sessionmaker) -> None:
    await _run(sessionmaker, "all-off")
    result = await _run(sessionmaker, "audit-all-on", dry_run=True)
    assert result.applied is False
    assert result.changes == []
    assert result.profile == "all-off"
    assert await _flags(sessionmaker) == dict.fromkeys(ALL_FLAGS, False)


async def test_concurrent_inits_exactly_one_wins(sessionmaker) -> None:
    for _ in range(5):
        async with sessionmaker() as db:
            await db.execute(delete(FeatureFlag))
            await db.execute(delete(FeatureFlagBootstrap))
            await db.execute(delete(AdminAuditEvent))
            await db.commit()
        results = await asyncio.gather(
            _run(sessionmaker, "all-off"),
            _run(sessionmaker, "audit-all-on"),
            _run(sessionmaker, "beta"),
        )
        winners = [r for r in results if r.applied]
        assert len(winners) == 1
        status = await _status(sessionmaker)
        assert status is not None
        assert status.profile == winners[0].profile
        assert await _flags(sessionmaker) == PROFILES[status.profile]
        assert {e.safe_metadata["profile"] for e in await _audits(sessionmaker)} == {status.profile}


async def test_cli_init_flags_applies_and_dry_run_is_readonly(
    sessionmaker, settings: Settings, monkeypatch, capsys
) -> None:
    monkeypatch.setattr("numra_api.cli.get_settings", lambda: settings)
    assert await init_flags("beta", dry_run=True) == 0
    assert "dry-run" in capsys.readouterr().out
    assert await _status(sessionmaker) is None

    assert await init_flags("beta") == 0
    assert {k for k, v in (await _flags(sessionmaker)).items() if v} == BETA_ON
    assert await init_flags("all-off") == 0  # No-op, Exit 0
    assert {k for k, v in (await _flags(sessionmaker)).items() if v} == BETA_ON


async def test_singleton_and_source_constraints(sessionmaker) -> None:
    from sqlalchemy.exc import IntegrityError

    await _run(sessionmaker, "all-off")
    async with sessionmaker() as db:
        db.add(FeatureFlagBootstrap(id=2, profile="x", source="bootstrap"))
        with pytest.raises(IntegrityError):
            await db.commit()
    async with sessionmaker() as db:
        await db.execute(delete(FeatureFlagBootstrap))
        db.add(FeatureFlagBootstrap(id=1, profile="x", source="bogus"))
        with pytest.raises(IntegrityError):
            await db.commit()
    async with sessionmaker() as db:
        assert (
            await db.execute(select(func.count()).select_from(FeatureFlagBootstrap))
        ).scalar() == 1
