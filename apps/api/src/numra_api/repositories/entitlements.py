from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import EntitlementAssignment, EntitlementSet
from numra_api.models.enums import BetaFeature
from numra_api.services.errors import NotFoundError

#: The one seeded `EntitlementSet` every user without an explicit `EntitlementAssignment`
#: falls back to (see alembic/versions -- seeded deterministically, and
#: get_effective_entitlement_set_for_user below).
DEFAULT_ENTITLEMENT_SET_KEY = "beta_default"

#: D4: an explicit assignment to this set IS the individual beta grant. The set's
#: cost-intensive columns (below) say what the grant covers; a user without any
#: assignment holds no grant, however permissive the display fallback above is.
BETA_ACCESS_SET_KEY = DEFAULT_ENTITLEMENT_SET_KEY

#: Which `EntitlementSet` column authorizes which cost-intensive feature group.
BETA_FEATURE_COLUMN = {
    BetaFeature.REPORT: "premium_reports",
    BetaFeature.ANALYSIS: "advanced_relationship_analysis",
    BetaFeature.COPILOT: "relationship_copilot",
}


async def user_has_beta_feature(
    db: AsyncSession, *, user_id: uuid.UUID, feature: BetaFeature
) -> bool:
    """True iff the user holds an explicit assignment whose set enables ``feature``."""
    column = getattr(EntitlementSet, BETA_FEATURE_COLUMN[feature])
    result = await db.execute(
        select(column)
        .select_from(EntitlementAssignment)
        .join(EntitlementSet, EntitlementAssignment.entitlement_set_id == EntitlementSet.id)
        .where(EntitlementAssignment.user_id == user_id)
    )
    return result.scalar_one_or_none() is True


async def has_beta_grant(db: AsyncSession, *, user_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(EntitlementAssignment.id).where(EntitlementAssignment.user_id == user_id)
    )
    return result.scalar_one_or_none() is not None


async def grant_beta_access(db: AsyncSession, *, user_id: uuid.UUID) -> bool:
    """Idempotent, race-safe (``ON CONFLICT DO NOTHING`` on the unique ``user_id``).
    Returns True only if this call created the assignment. Caller commits."""
    beta_set = await get_entitlement_set_by_key(db, key=BETA_ACCESS_SET_KEY)
    if beta_set is None:
        raise NotFoundError(f"entitlement set {BETA_ACCESS_SET_KEY!r} not found")
    result = await db.execute(
        pg_insert(EntitlementAssignment)
        .values(user_id=user_id, entitlement_set_id=beta_set.id)
        .on_conflict_do_nothing(index_elements=["user_id"])
        .returning(EntitlementAssignment.id)
    )
    return result.scalar_one_or_none() is not None


async def revoke_beta_access(db: AsyncSession, *, user_id: uuid.UUID) -> bool:
    """Idempotent. Returns True only if this call removed an assignment. Caller commits."""
    result = await db.execute(
        delete(EntitlementAssignment)
        .where(EntitlementAssignment.user_id == user_id)
        .returning(EntitlementAssignment.id)
    )
    return result.scalar_one_or_none() is not None


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
