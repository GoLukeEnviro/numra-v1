from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import ConsentEvent, ConsentGrant


async def create_consent_grant(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    grantor_user_id: uuid.UUID,
    grantee_user_id: uuid.UUID,
    scope: str,
) -> ConsentGrant:
    grant = ConsentGrant(
        workspace_id=workspace_id,
        grantor_user_id=grantor_user_id,
        grantee_user_id=grantee_user_id,
        scope=scope,
        version=1,
    )
    db.add(grant)
    await db.flush()
    return grant


async def get_active_grant(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    grantor_user_id: uuid.UUID,
    grantee_user_id: uuid.UUID,
    scope: str,
) -> ConsentGrant | None:
    """The one enforcement read path -- always hits the DB fresh (no caching layer),
    see services/consent_service.py::assert_consent. `ORDER BY version DESC LIMIT 1`
    tolerates a future re-grant flow even though this PR always writes version=1."""
    stmt = (
        select(ConsentGrant)
        .where(
            ConsentGrant.workspace_id == workspace_id,
            ConsentGrant.grantor_user_id == grantor_user_id,
            ConsentGrant.grantee_user_id == grantee_user_id,
            ConsentGrant.scope == scope,
            ConsentGrant.revoked_at.is_(None),
        )
        .order_by(ConsentGrant.version.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_grant_for_key(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    grantor_user_id: uuid.UUID,
    grantee_user_id: uuid.UUID,
    scope: str,
) -> ConsentGrant | None:
    """Like `get_active_grant` but WITHOUT the `revoked_at IS NULL` filter -- returns
    the row that owns the `uq_consent_grants_workspace_grantor_grantee_scope_version`
    slot regardless of its revoked state, so `grant_consent` can reactivate a
    previously revoked grant instead of colliding on INSERT."""
    stmt = (
        select(ConsentGrant)
        .where(
            ConsentGrant.workspace_id == workspace_id,
            ConsentGrant.grantor_user_id == grantor_user_id,
            ConsentGrant.grantee_user_id == grantee_user_id,
            ConsentGrant.scope == scope,
        )
        .order_by(ConsentGrant.version.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def reactivate_grant(db: AsyncSession, *, grant: ConsentGrant) -> ConsentGrant:
    grant.revoked_at = None
    await db.flush()
    await db.refresh(grant)
    return grant


async def get_grant_for_workspace(
    db: AsyncSession, *, grant_id: uuid.UUID, workspace_id: uuid.UUID
) -> ConsentGrant | None:
    stmt = select(ConsentGrant).where(
        ConsentGrant.id == grant_id, ConsentGrant.workspace_id == workspace_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_grants_for_workspace(
    db: AsyncSession, *, workspace_id: uuid.UUID
) -> list[ConsentGrant]:
    stmt = select(ConsentGrant).where(ConsentGrant.workspace_id == workspace_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def revoke_grant(db: AsyncSession, *, grant: ConsentGrant, now: dt.datetime) -> ConsentGrant:
    grant.revoked_at = now
    await db.flush()
    await db.refresh(grant)
    return grant


async def revoke_all_active_grants_for_workspace(
    db: AsyncSession, *, workspace_id: uuid.UUID, now: dt.datetime
) -> list[ConsentGrant]:
    """PR-V2-10 -- kaskadierender Revoke für Dissolution/Account-Deletion: ein
    einziges `UPDATE ... WHERE workspace_id=? AND revoked_at IS NULL RETURNING *`
    revoked jede aktive `ConsentGrant`-Row des Workspace, beide Richtungen, alle
    Scopes. Der Aufrufer (services/connection_service.py::dissolve_own_connection,
    services/account_deletion_service.py::delete_own_account) fügt für jede
    zurückgegebene Row anschließend ein `ConsentEvent(REVOKED)` ein -- ein Event pro
    Grant, gemäß dem bestehenden "jeder Revoke hat ein Event"-Invariant
    (repositories/consent.py::revoke_grant)."""
    stmt = (
        update(ConsentGrant)
        .where(ConsentGrant.workspace_id == workspace_id, ConsentGrant.revoked_at.is_(None))
        .values(revoked_at=now)
        .returning(ConsentGrant)
    )
    result = await db.execute(stmt)
    await db.flush()
    return list(result.scalars().all())


async def create_consent_event(
    db: AsyncSession,
    *,
    grant_id: uuid.UUID,
    event_type: str,
    actor_user_id: uuid.UUID | None,
) -> ConsentEvent:
    event = ConsentEvent(grant_id=grant_id, event_type=event_type, actor_user_id=actor_user_id)
    db.add(event)
    await db.flush()
    return event
