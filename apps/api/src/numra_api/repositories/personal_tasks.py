from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import PersonalTask
from numra_api.models.enums import PersonalTaskStatus


async def create_personal_task(
    db: AsyncSession, *, user_id: uuid.UUID, person_id: uuid.UUID, **fields: Any
) -> PersonalTask:
    task = PersonalTask(user_id=user_id, person_id=person_id, **fields)
    db.add(task)
    await db.flush()
    return task


async def get_personal_task_for_user(
    db: AsyncSession, *, task_id: uuid.UUID, user_id: uuid.UUID
) -> PersonalTask | None:
    stmt = select(PersonalTask).where(PersonalTask.id == task_id, PersonalTask.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_personal_tasks_for_person(
    db: AsyncSession,
    *,
    person_id: uuid.UUID,
    user_id: uuid.UUID,
    status: PersonalTaskStatus | None,
    limit: int,
    offset: int,
) -> list[PersonalTask]:
    stmt = select(PersonalTask).where(
        PersonalTask.person_id == person_id, PersonalTask.user_id == user_id
    )
    if status is not None:
        stmt = stmt.where(PersonalTask.status == status)
    stmt = stmt.order_by(PersonalTask.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_personal_task(
    db: AsyncSession, *, task: PersonalTask, **fields: Any
) -> PersonalTask:
    for key, value in fields.items():
        setattr(task, key, value)
    await db.flush()
    await db.refresh(task)
    return task


async def delete_personal_task(db: AsyncSession, *, task: PersonalTask) -> None:
    await db.delete(task)
