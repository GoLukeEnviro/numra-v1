"""Einmaliger Flag-Bootstrap (Plan v4 Variante A).

Entscheidend ist allein die Existenz der Singleton-Zeile in `feature_flag_bootstrap`.
Wer sie per `INSERT ... ON CONFLICT DO NOTHING` anlegt, gewinnt und setzt die
Profilwerte in DERSELBEN Transaktion; konkurrierende Inits warten am Unique-Index bis
zum Commit und werden dann zum No-op. `updated_by_user_id IS NULL` ist bewusst KEIN
Kriterium (FK ON DELETE SET NULL).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.feature_flag_profiles import PROFILES
from numra_api.models import FeatureFlag, FeatureFlagBootstrap
from numra_api.models.enums import AuditAction
from numra_api.repositories.audit import record_audit_event

logger = logging.getLogger(__name__)


class ProfileRequiredError(Exception):
    """Status fehlt und kein Profil angegeben: bewusst kein stilles Default-Profil."""


@dataclass(frozen=True)
class FlagChange:
    name: str
    before: bool | None
    after: bool


@dataclass
class BootstrapResult:
    applied: bool
    profile: str | None
    status_source: str | None
    changes: list[FlagChange] = field(default_factory=list)


def _diff(current: dict[str, bool], target: dict[str, bool]) -> list[FlagChange]:
    return [
        FlagChange(name, current.get(name), value)
        for name, value in target.items()
        if current.get(name) != value
    ]


async def bootstrap_flags(
    db: AsyncSession, *, profile: str | None, dry_run: bool = False
) -> BootstrapResult:
    """`profile=None` ist nur zulaessig, solange ein Status existiert (No-op) oder bei
    `dry_run`; fehlt der Status, bricht der Claim-Pfad VOR dem INSERT ab."""
    if profile is not None and profile not in PROFILES:
        raise ValueError(f"unknown profile: {profile!r} (known: {sorted(PROFILES)})")

    if dry_run or profile is None:
        status = (await db.execute(select(FeatureFlagBootstrap))).scalar_one_or_none()
        if status is not None:
            return BootstrapResult(False, status.profile, status.source)
        if profile is None:
            if dry_run:
                return BootstrapResult(False, None, None)
            raise ProfileRequiredError(
                "Profil nötig, Status fehlt: --profile bzw. NUMRA_FLAGS_PROFILE setzen "
                f"({', '.join(sorted(PROFILES))})"
            )
    assert profile is not None
    target = PROFILES[profile]

    if dry_run:
        current = {f.name: f.enabled for f in (await db.execute(select(FeatureFlag))).scalars()}
        return BootstrapResult(False, profile, None, _diff(current, target))

    claimed = await db.execute(
        insert(FeatureFlagBootstrap)
        .values(id=1, profile=profile, source="bootstrap")
        .on_conflict_do_nothing(index_elements=["id"])
        .returning(FeatureFlagBootstrap.id)
    )
    if claimed.scalar_one_or_none() is None:
        await db.rollback()
        status = (await db.execute(select(FeatureFlagBootstrap))).scalar_one()
        if status.source == "bootstrap" and status.profile != profile:
            logger.warning(
                "flag bootstrap already done with profile %r (source %s); requested profile "
                "%r is NOT applied -- change flags via /admin/flags",
                status.profile,
                status.source,
                profile,
            )
        return BootstrapResult(False, status.profile, status.source)

    current = {
        f.name: f.enabled
        for f in (await db.execute(select(FeatureFlag).with_for_update())).scalars()
    }
    changes = _diff(current, target)
    for change in changes:
        await db.execute(
            insert(FeatureFlag)
            .values(name=change.name, enabled=change.after, updated_by_user_id=None)
            .on_conflict_do_update(
                index_elements=["name"],
                set_={"enabled": change.after, "updated_at": func.now()},
            )
        )
        await record_audit_event(
            db,
            actor_user_id=None,
            action=AuditAction.FEATURE_FLAG_CHANGED,
            target_user_id=None,
            safe_metadata={
                "origin": "bootstrap",
                "profile": profile,
                "flag": change.name,
                "from": change.before,
                "to": change.after,
            },
        )
    await db.commit()
    return BootstrapResult(True, profile, "bootstrap", changes)
