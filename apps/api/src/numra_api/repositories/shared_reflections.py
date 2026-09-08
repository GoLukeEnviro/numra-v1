"""PR-V2-08 -- specs/v2/personal-workspace-spec.md SHARE flow. `SharedReflection`
is workspace-wide visible to any ACTIVE member (no proposer/recipient split) --
callers gate on `get_workspace_member` first (IDOR anti-enumeration), same
discipline as repositories/workspace_tasks.py. No update function -- immutable
after creation (no PATCH route, see models/tables.py::SharedReflection).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import SharedReflection


async def create_shared_reflection(db: AsyncSession, **fields: Any) -> SharedReflection:
    reflection = SharedReflection(**fields)
    db.add(reflection)
    await db.flush()
    return reflection


async def get_shared_reflection_for_workspace(
    db: AsyncSession, *, reflection_id: uuid.UUID, workspace_id: uuid.UUID
) -> SharedReflection | None:
    stmt = select(SharedReflection).where(
        SharedReflection.id == reflection_id, SharedReflection.workspace_id == workspace_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_shared_reflections_for_workspace(
    db: AsyncSession, *, workspace_id: uuid.UUID, limit: int, offset: int
) -> list[SharedReflection]:
    stmt = (
        select(SharedReflection)
        .where(SharedReflection.workspace_id == workspace_id)
        .order_by(SharedReflection.entry_date.desc(), SharedReflection.shared_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def delete_shared_reflection(db: AsyncSession, *, reflection: SharedReflection) -> None:
    await db.delete(reflection)
