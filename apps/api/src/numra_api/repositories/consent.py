from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
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
