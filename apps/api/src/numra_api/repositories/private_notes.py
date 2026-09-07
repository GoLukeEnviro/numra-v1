from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import PrivateNote


async def create_private_note(
    db: AsyncSession, *, user_id: uuid.UUID, person_id: uuid.UUID, **fields: Any
) -> PrivateNote:
    note = PrivateNote(user_id=user_id, person_id=person_id, **fields)
    db.add(note)
    await db.flush()
    return note


async def get_private_note_for_user(
    db: AsyncSession, *, note_id: uuid.UUID, user_id: uuid.UUID
) -> PrivateNote | None:
    stmt = select(PrivateNote).where(PrivateNote.id == note_id, PrivateNote.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_private_notes_for_person(
    db: AsyncSession, *, person_id: uuid.UUID, user_id: uuid.UUID, limit: int, offset: int
) -> list[PrivateNote]:
    stmt = (
        select(PrivateNote)
        .where(PrivateNote.person_id == person_id, PrivateNote.user_id == user_id)
        .order_by(PrivateNote.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_private_note(db: AsyncSession, *, note: PrivateNote, **fields: Any) -> PrivateNote:
    for key, value in fields.items():
        setattr(note, key, value)
    await db.flush()
    await db.refresh(note)
    return note


async def delete_private_note(db: AsyncSession, *, note: PrivateNote) -> None:
    await db.delete(note)
