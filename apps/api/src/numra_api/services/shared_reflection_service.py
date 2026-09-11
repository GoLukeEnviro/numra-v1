"""PR-V2-08 -- specs/v2/personal-workspace-spec.md SHARE flow. The ONLY creation
path for a `SharedReflection` is `share_private_reflection` -- it copies
`entry_date`/`content` from the caller's own `PrivateReflection` (IDOR-gated via
`get_private_reflection_for_user`) into a new snapshot row, never a live link (a
later edit/delete of the source never changes the shared copy). No
consent-scope gate is required beyond plain workspace membership -- the explicit
SHARE click IS the consent act (specs/v2/consent-spec.md is not in scope here,
same rationale as `WorkspaceTask`'s JOINT_SHARED path)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

import numra_api.repositories.shared_reflections as shared_reflections_repo
from numra_api.models import SharedReflection
from numra_api.repositories.private_reflections import get_private_reflection_for_user
from numra_api.repositories.workspaces import get_workspace_member
from numra_api.services.errors import NotFoundError
from numra_api.services.workspace_guard import assert_workspace_active_by_id


def _require_member(member: object, *, workspace_id: uuid.UUID) -> None:
    if member is None:
        # IDOR-anti-enumeration -- never 403, see services/workspace_task_service.py.
        raise NotFoundError(f"workspace {workspace_id} not found")


def _require_reflection(
    reflection: SharedReflection | None, *, reflection_id: uuid.UUID
) -> SharedReflection:
    if reflection is None:
        raise NotFoundError(f"shared reflection {reflection_id} not found")
    return reflection


async def share_private_reflection(
    db: AsyncSession,
    *,
    reflection_id: uuid.UUID,
    user_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> SharedReflection:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    await assert_workspace_active_by_id(db, workspace_id=workspace_id)

    source = await get_private_reflection_for_user(db, reflection_id=reflection_id, user_id=user_id)
    if source is None:
        raise NotFoundError(f"private reflection {reflection_id} not found")

    return await shared_reflections_repo.create_shared_reflection(
        db,
        workspace_id=workspace_id,
        author_user_id=user_id,
        source_private_reflection_id=source.id,
        entry_date=source.entry_date,
        content=source.content,
    )


async def get_shared_reflection(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, reflection_id: uuid.UUID
) -> SharedReflection:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    reflection = await shared_reflections_repo.get_shared_reflection_for_workspace(
        db, reflection_id=reflection_id, workspace_id=workspace_id
    )
    return _require_reflection(reflection, reflection_id=reflection_id)


async def list_shared_reflections(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, limit: int, offset: int
) -> list[SharedReflection]:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    return await shared_reflections_repo.list_shared_reflections_for_workspace(
        db, workspace_id=workspace_id, limit=limit, offset=offset
    )


async def delete_shared_reflection(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID, reflection_id: uuid.UUID
) -> None:
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    _require_member(member, workspace_id=workspace_id)

    reflection = await shared_reflections_repo.get_shared_reflection_for_workspace(
        db, reflection_id=reflection_id, workspace_id=workspace_id
    )
    reflection = _require_reflection(reflection, reflection_id=reflection_id)

    if reflection.author_user_id != user_id:
        # Same IDOR-anti-enumeration rationale as workspace_task_service.py's
        # self-accept guard -- a non-author's DELETE reads as not-found, never a
        # 403 that would confirm the row exists.
        raise NotFoundError(f"shared reflection {reflection_id} not found")

    await assert_workspace_active_by_id(db, workspace_id=workspace_id)
    await shared_reflections_repo.delete_shared_reflection(db, reflection=reflection)


__all__ = [
    "delete_shared_reflection",
    "get_shared_reflection",
    "list_shared_reflections",
    "share_private_reflection",
]
