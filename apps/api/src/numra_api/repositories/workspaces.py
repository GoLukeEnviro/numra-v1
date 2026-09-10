from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import Person, RelationshipWorkspace, WorkspaceMember
from numra_api.models.enums import PersonAccountMode, WorkspaceMemberStatus, WorkspaceStatus


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


async def conditionally_dissolve_workspace(
    db: AsyncSession, *, workspace_id: uuid.UUID, now: dt.datetime
) -> bool:
    """Atomic `UPDATE ... WHERE id=? AND status='ACTIVE'` -- TOCTOU-safe, not a plain
    read-then-setattr-then-flush (PR-V2-10), same discipline as
    repositories/workspace_tasks.py::conditionally_transition_status. `False` means
    the workspace was already DISSOLVED -- every caller (e.g.
    services/connection_service.py::dissolve_own_connection,
    services/account_deletion_service.py) treats that as an idempotent no-op, never
    a conflict."""
    stmt = (
        update(RelationshipWorkspace)
        .where(
            RelationshipWorkspace.id == workspace_id,
            RelationshipWorkspace.status == WorkspaceStatus.ACTIVE,
        )
        .values(status=WorkspaceStatus.DISSOLVED, dissolved_at=now)
        .returning(RelationshipWorkspace.id)
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.scalar_one_or_none() is not None


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
    stmt = (
        select(WorkspaceMember)
        .where(WorkspaceMember.workspace_id == workspace_id)
        .order_by(WorkspaceMember.joined_at, WorkspaceMember.id)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_workspace_by_id(
    db: AsyncSession, *, workspace_id: uuid.UUID
) -> RelationshipWorkspace | None:
    return await db.get(RelationshipWorkspace, workspace_id)


async def list_workspaces_for_user(
    db: AsyncSession, *, user_id: uuid.UUID
) -> list[RelationshipWorkspace]:
    """Every `RelationshipWorkspace` where `user_id` has an ACTIVE `WorkspaceMember`
    row -- ACTIVE membership survives a workspace-level DISSOLVE (only
    `RelationshipWorkspace.status` changes then, see `dissolve_workspace`), so this
    intentionally still lists dissolved workspaces (read-only history)."""
    stmt = (
        select(RelationshipWorkspace)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == RelationshipWorkspace.id)
        .where(
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
        )
        .order_by(RelationshipWorkspace.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_relationship_type(
    db: AsyncSession, *, workspace: RelationshipWorkspace, relationship_type: str
) -> RelationshipWorkspace:
    workspace.relationship_type = relationship_type
    await db.flush()
    await db.refresh(workspace)
    return workspace


async def get_self_person_for_member(db: AsyncSession, *, user_id: uuid.UUID) -> Person | None:
    """The one `SELF`-mode Person representing `user_id` (uniqueness DB-enforced by
    `uq_people_user_id_self_mode`, see models/tables.py::Person). Returns `None`, not
    an error, when the user has never created a Person -- callers (e.g.
    services/relationship_workspace_service.py) must render `self_person: null` for
    that case, never a 500."""
    stmt = select(Person).where(
        Person.user_id == user_id, Person.person_account_mode == PersonAccountMode.SELF
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
