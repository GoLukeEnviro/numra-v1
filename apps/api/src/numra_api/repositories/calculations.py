from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import Calculation, Person


async def create_calculation(
    db: AsyncSession,
    *,
    person_id: uuid.UUID,
    calculation_version: str,
    schema_version: str,
    as_of_date: Any,
    input_snapshot: dict[str, Any],
    canonical_profile_json: dict[str, Any],
    deterministic_hash: str,
) -> Calculation:
    calculation = Calculation(
        person_id=person_id,
        calculation_version=calculation_version,
        schema_version=schema_version,
        as_of_date=as_of_date,
        input_snapshot=input_snapshot,
        canonical_profile_json=canonical_profile_json,
        deterministic_hash=deterministic_hash,
    )
    db.add(calculation)
    await db.flush()
    return calculation


async def get_calculation_for_user(
    db: AsyncSession, *, calculation_id: uuid.UUID, user_id: uuid.UUID
) -> Calculation | None:
    stmt = (
        select(Calculation)
        .join(Person, Person.id == Calculation.person_id)
        .where(Calculation.id == calculation_id, Person.user_id == user_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_latest_calculation_for_person(
    db: AsyncSession, *, person_id: uuid.UUID, user_id: uuid.UUID
) -> Calculation | None:
    stmt = (
        select(Calculation)
        .join(Person, Person.id == Calculation.person_id)
        .where(Calculation.person_id == person_id, Person.user_id == user_id)
        .order_by(Calculation.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_calculations_for_person(
    db: AsyncSession, *, person_id: uuid.UUID, user_id: uuid.UUID, limit: int, offset: int
) -> list[Calculation]:
    """Ownership is enforced via the `Person.user_id` join, not by trusting the
    caller's `person_id` alone — a person_id belonging to a different user yields an
    empty list, not another user's calculations."""
    stmt = (
        select(Calculation)
        .join(Person, Person.id == Calculation.person_id)
        .where(Calculation.person_id == person_id, Person.user_id == user_id)
        .order_by(Calculation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
