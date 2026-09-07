from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import EntitlementAssignment, EntitlementSet

#: The one seeded `EntitlementSet` every user without an explicit `EntitlementAssignment`
#: falls back to (see alembic/versions -- seeded deterministically, and
#: get_effective_entitlement_set_for_user below).
DEFAULT_ENTITLEMENT_SET_KEY = "beta_default"


async def get_entitlement_set_by_key(db: AsyncSession, *, key: str) -> EntitlementSet | None:
    result = await db.execute(select(EntitlementSet).where(EntitlementSet.key == key))
    return result.scalar_one_or_none()


async def get_effective_entitlement_set_for_user(
    db: AsyncSession, *, user_id: uuid.UUID
) -> EntitlementSet | None:
    """The `EntitlementSet` GET /v1/me/entitlements resolves to: the user's explicit
    `EntitlementAssignment` if one exists, otherwise the seeded
    `DEFAULT_ENTITLEMENT_SET_KEY` set. Returns ``None`` only if even the default set is
    somehow missing (a seed/migration inconsistency, not a normal runtime state)."""
    result = await db.execute(
        select(EntitlementSet)
        .join(EntitlementAssignment, EntitlementAssignment.entitlement_set_id == EntitlementSet.id)
        .where(EntitlementAssignment.user_id == user_id)
    )
    assigned = result.scalar_one_or_none()
    if assigned is not None:
        return assigned
    return await get_entitlement_set_by_key(db, key=DEFAULT_ENTITLEMENT_SET_KEY)
