from __future__ import annotations

import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from numra_api.models import Calculation, Person, RelationshipComparison


def _relationship_with_people_stmt() -> Select[tuple[RelationshipComparison, Person, Person]]:
    """Shared join: resolves both participants' `Person` rows in one query so the
    frontend never needs a browser-only cache to know who Person A/B are.
    `RelationshipComparison.user_id` is the ownership scope -- both calculations were
    already verified to belong to this user at creation time
    (`routes/relationships.py`), so no further ownership check is needed on the join.
    """
    calc_a = aliased(Calculation)
    calc_b = aliased(Calculation)
    person_a = aliased(Person)
    person_b = aliased(Person)
    return (
        select(RelationshipComparison, person_a, person_b)
        .join(calc_a, calc_a.id == RelationshipComparison.calculation_a_id)
        .join(calc_b, calc_b.id == RelationshipComparison.calculation_b_id)
        .join(person_a, person_a.id == calc_a.person_id)
        .join(person_b, person_b.id == calc_b.person_id)
    )


async def get_relationship_with_people_for_user(
    db: AsyncSession, *, relationship_id: uuid.UUID, user_id: uuid.UUID
) -> tuple[RelationshipComparison, Person, Person] | None:
    stmt = _relationship_with_people_stmt().where(
        RelationshipComparison.id == relationship_id, RelationshipComparison.user_id == user_id
    )
    result = await db.execute(stmt)
    row = result.first()
    return (row[0], row[1], row[2]) if row is not None else None


async def list_relationships_for_user(
    db: AsyncSession, *, user_id: uuid.UUID, limit: int, offset: int
) -> list[tuple[RelationshipComparison, Person, Person]]:
    stmt = (
        _relationship_with_people_stmt()
        .where(RelationshipComparison.user_id == user_id)
        .order_by(RelationshipComparison.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return [(rel, pa, pb) for rel, pa, pb in result.all()]
