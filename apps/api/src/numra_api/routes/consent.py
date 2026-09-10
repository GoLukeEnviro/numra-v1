from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, require_csrf
from numra_api.models import ConsentGrant, User
from numra_api.schemas.consent import (
    ConsentGrantOut,
    ConsentGrantRequest,
    ConsentRevokeRequest,
    WorkspaceConsentOut,
)
from numra_api.services.consent_service import (
    grant_consent,
    list_consent_for_workspace_member,
    revoke_consent,
)
from numra_api.services.errors import ConsentGrantConflict
from numra_api.services.feature_flags import require_v2_phase

router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}/consent",
    tags=["consent"],
    dependencies=[Depends(require_v2_phase("connections"))],
)


def _grant_to_out(grant: ConsentGrant) -> ConsentGrantOut:
    return ConsentGrantOut.model_validate(grant, from_attributes=True)


@router.get("", response_model=WorkspaceConsentOut)
async def list_workspace_consent_route(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> WorkspaceConsentOut:
    grants = await list_consent_for_workspace_member(db, workspace_id=workspace_id, user_id=user.id)
    return WorkspaceConsentOut(
        granted_by_me=[_grant_to_out(g) for g in grants if g.grantor_user_id == user.id],
        granted_to_me=[_grant_to_out(g) for g in grants if g.grantee_user_id == user.id],
    )


@router.post(
    "/grant", response_model=ConsentGrantOut, status_code=201, dependencies=[Depends(require_csrf)]
)
async def grant_consent_route(
    workspace_id: uuid.UUID,
    body: ConsentGrantRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> ConsentGrantOut:
    try:
        grant = await grant_consent(
            db, workspace_id=workspace_id, grantor_user_id=user.id, scope=body.scope
        )
    except IntegrityError as exc:
        # The reactivate/create branch in grant_consent lost a race to a concurrent
        # grant for the same slot; the unique index is the only real arbiter, and
        # losing that race must surface as 409, never a raw driver 500 (same pattern
        # as routes/auth.py::register).
        await db.rollback()
        raise ConsentGrantConflict("consent for this scope was just granted") from exc
    return _grant_to_out(grant)


@router.post("/revoke", response_model=ConsentGrantOut, dependencies=[Depends(require_csrf)])
async def revoke_consent_route(
    workspace_id: uuid.UUID,
    body: ConsentRevokeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> ConsentGrantOut:
    grant = await revoke_consent(
        db, workspace_id=workspace_id, grantor_user_id=user.id, scope=body.scope
    )
    return _grant_to_out(grant)
