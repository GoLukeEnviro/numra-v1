from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import RelationshipWorkspace, WorkspaceMember
from numra_api.models.enums import WorkspaceMemberStatus, WorkspaceStatus


async def create_relationship_workspace(
    db: AsyncSession, *, connection_id: uuid.UUID
) -> RelationshipWorkspace:
    workspace = RelationshipWorkspace(connection_id=connection_id)
    db.add(workspace)
    await db.flush()
    return workspace


async def get_workspace_for_connection(
    db: AsyncSession, *, connection_id: uuid.UUID
) -> RelationshipWorkspace | None:
    stmt = select(RelationshipWorkspace).where(RelationshipWorkspace.connection_id == connection_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def dissolve_workspace(
    db: AsyncSession, *, workspace: RelationshipWorkspace, now: dt.datetime
) -> RelationshipWorkspace:
    workspace.status = WorkspaceStatus.DISSOLVED
    workspace.dissolved_at = now
    await db.flush()
    await db.refresh(workspace)
    return workspace


async def create_workspace_member(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceMember:
    member = WorkspaceMember(workspace_id=workspace_id, user_id=user_id)
    db.add(member)
    await db.flush()
    return member


async def get_workspace_member(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> WorkspaceMember | None:
    """Existence check used as the IDOR gate before every consent read/mutation on a
    workspace (routes/consent.py) -- filters `workspace_id` AND `user_id` in the same
    statement."""
    stmt = select(WorkspaceMember).where(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user_id,
        WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_workspace_members(
    db: AsyncSession, *, workspace_id: uuid.UUID
) -> list[WorkspaceMember]:
    stmt = select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())
