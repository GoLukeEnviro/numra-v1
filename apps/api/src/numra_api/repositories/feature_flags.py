"""DB-backed Feature-Flag-Zugriff. `action`-Spalte von `AdminAuditEvent` ist ein
reines `String(50)` ohne natives Postgres-Enum (siehe `models/tables.py`), daher
braucht `AuditAction.FEATURE_FLAG_CHANGED` keine eigene Migration."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import FeatureFlag
from numra_api.models.enums import AuditAction
from numra_api.repositories.audit import record_audit_event
from numra_api.services.errors import NotFoundError


async def get_all_flags(db: AsyncSession) -> dict[str, bool]:
    result = await db.execute(select(FeatureFlag))
    return {row.name: row.enabled for row in result.scalars()}


async def get_all_flags_with_metadata(db: AsyncSession) -> list[FeatureFlag]:
    result = await db.execute(select(FeatureFlag).order_by(FeatureFlag.name))
    return list(result.scalars())


async def set_flag(
    db: AsyncSession, *, name: str, enabled: bool, actor_user_id: uuid.UUID
) -> None:
    flag = await db.get(FeatureFlag, name)
    if flag is None:
        raise NotFoundError(f"unknown flag: {name}")
    previous = flag.enabled
    flag.enabled = enabled
    flag.updated_by_user_id = actor_user_id
    await record_audit_event(
        db,
        actor_user_id=actor_user_id,
        action=AuditAction.FEATURE_FLAG_CHANGED,
        target_user_id=None,
        safe_metadata={"flag": name, "from": previous, "to": enabled},
    )
    await db.commit()
