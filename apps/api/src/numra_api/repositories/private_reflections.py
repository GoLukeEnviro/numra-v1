from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import PrivateReflection


async def create_private_reflection(
    db: AsyncSession, *, user_id: uuid.UUID, person_id: uuid.UUID, **fields: Any
) -> PrivateReflection:
    reflection = PrivateReflection(user_id=user_id, person_id=person_id, **fields)
    db.add(reflection)
    await db.flush()
    return reflection


async def get_private_reflection_for_user(
    db: AsyncSession, *, reflection_id: uuid.UUID, user_id: uuid.UUID
) -> PrivateReflection | None:
    stmt = select(PrivateReflection).where(
        PrivateReflection.id == reflection_id, PrivateReflection.user_id == user_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_private_reflections_for_person(
    db: AsyncSession, *, person_id: uuid.UUID, user_id: uuid.UUID, limit: int, offset: int
) -> list[PrivateReflection]:
    stmt = (
        select(PrivateReflection)
        .where(PrivateReflection.person_id == person_id, PrivateReflection.user_id == user_id)
        .order_by(PrivateReflection.entry_date.desc(), PrivateReflection.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_private_reflection(
    db: AsyncSession, *, reflection: PrivateReflection, **fields: Any
) -> PrivateReflection:
    for key, value in fields.items():
        setattr(reflection, key, value)
    await db.flush()
    await db.refresh(reflection)
    return reflection


async def delete_private_reflection(db: AsyncSession, *, reflection: PrivateReflection) -> None:
    await db.delete(reflection)
