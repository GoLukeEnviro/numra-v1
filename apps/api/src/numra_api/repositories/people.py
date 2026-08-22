from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import Person


async def create_person(db: AsyncSession, *, user_id: uuid.UUID, **fields: Any) -> Person:
    person = Person(user_id=user_id, **fields)
    db.add(person)
    await db.flush()
    return person


async def get_person(
    db: AsyncSession, *, person_id: uuid.UUID, user_id: uuid.UUID
) -> Person | None:
    stmt = select(Person).where(Person.id == person_id, Person.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_people(db: AsyncSession, *, user_id: uuid.UUID) -> list[Person]:
    stmt = select(Person).where(Person.user_id == user_id).order_by(Person.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_person(db: AsyncSession, *, person: Person, **fields: Any) -> Person:
    """`fields` must already be filtered to only what the caller actually intends to
    change (see `routes/people.py::patch_person_route`'s `model_fields_set` check) --
    this applies every value verbatim, `None` included, so a client can genuinely
    clear a nullable field (e.g. `birth_middle_names`) rather than have that silently
    ignored."""
    for key, value in fields.items():
        setattr(person, key, value)
    await db.flush()
    await db.refresh(person)
    return person


async def delete_person(db: AsyncSession, *, person: Person) -> None:
    await db.delete(person)
