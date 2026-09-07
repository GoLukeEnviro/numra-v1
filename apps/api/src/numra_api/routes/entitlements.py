from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db
from numra_api.models import User
from numra_api.repositories.entitlements import get_effective_entitlement_set_for_user
from numra_api.schemas.entitlements import EntitlementSetOut
from numra_api.services.errors import NotFoundError

router = APIRouter(prefix="/v1/me", tags=["entitlements"])


@router.get("/entitlements", response_model=EntitlementSetOut)
async def get_my_entitlements(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EntitlementSetOut:
    """The signed-in user's effective feature/limit bundle: their explicit
    `EntitlementAssignment` if one exists, otherwise the seeded "beta_default"
    `EntitlementSet` (see repositories/entitlements.py). A missing default set is a
    seed/migration inconsistency, not a normal runtime state -- surfaced as 404 rather
    than silently defaulting to some hardcoded shape."""
    entitlement_set = await get_effective_entitlement_set_for_user(db, user_id=user.id)
    if entitlement_set is None:
        raise NotFoundError("no entitlement set resolved for this user")
    return EntitlementSetOut(
        personal_workspace=entitlement_set.personal_workspace,
        connections=entitlement_set.connections,
        relationship_workspaces=entitlement_set.relationship_workspaces,
        relationship_checkins=entitlement_set.relationship_checkins,
        relationship_copilot=entitlement_set.relationship_copilot,
        advanced_relationship_analysis=entitlement_set.advanced_relationship_analysis,
        life_tracking=entitlement_set.life_tracking,
        premium_reports=entitlement_set.premium_reports,
        max_connections=entitlement_set.max_connections,
        max_workspaces=entitlement_set.max_workspaces,
    )
