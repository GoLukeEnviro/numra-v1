"""PR-V2-09 -- persistence for `ChatThread`/`ChatMessage`/`ThreadSummary`/
`ThreadContextSnapshot`.

IDOR/isolation discipline (specs/v2/privacy-spec.md Section 49, specs/v2/
copilot-grounding-spec.md): every "list threads"/"read messages" query here is
scoped by `workspace_id`/`owner_user_id`/membership, never by `thread_id` alone --
callers additionally gate on `get_workspace_member` before calling in (same pattern
as `repositories/relationship_roadmaps.py`). Every `ThreadSummary`/
`ThreadContextSnapshot` query filters `thread_id` AND `scope` together (defense in
depth against a future bug that mixes up thread ids across scopes), never
`thread_id` alone -- see `models/tables.py::ThreadSummary`/`ThreadContextSnapshot`
docstrings.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import (
    ChatMessage,
    ChatThread,
    CheckinAnalysis,
    RelationshipCheckin,
    ThreadContextSnapshot,
    ThreadSummary,
)
from numra_api.models.enums import ThreadScope


async def get_shared_thread_for_workspace(
    db: AsyncSession, *, workspace_id: uuid.UUID
) -> ChatThread | None:
    """The one non-archived RELATIONSHIP_SHARED thread for a workspace, if any --
    at most one can exist (`uq_chat_threads_one_shared_per_workspace`)."""
    stmt = select(ChatThread).where(
        ChatThread.workspace_id == workspace_id,
        ChatThread.scope == ThreadScope.RELATIONSHIP_SHARED,
        ChatThread.archived_at.is_(None),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_private_thread_for_owner(
    db: AsyncSession, *, workspace_id: uuid.UUID, owner_user_id: uuid.UUID
) -> ChatThread | None:
    """The one non-archived RELATIONSHIP_PRIVATE thread for (workspace, owner), if
    any -- at most one can exist (`uq_chat_threads_one_private_per_owner`). Never
    call this with another user's `owner_user_id` to "peek" -- the route/service
    layer always derives `owner_user_id` from the authenticated caller."""
    stmt = select(ChatThread).where(
        ChatThread.workspace_id == workspace_id,
        ChatThread.owner_user_id == owner_user_id,
        ChatThread.scope == ThreadScope.RELATIONSHIP_PRIVATE,
        ChatThread.archived_at.is_(None),
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_thread(db: AsyncSession, **fields: Any) -> ChatThread:
    thread = ChatThread(**fields)
    db.add(thread)
    await db.flush()
    return thread


async def get_thread_for_workspace(
    db: AsyncSession, *, thread_id: uuid.UUID, workspace_id: uuid.UUID
) -> ChatThread | None:
    stmt = select(ChatThread).where(
        ChatThread.id == thread_id, ChatThread.workspace_id == workspace_id
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def archive_thread(db: AsyncSession, *, thread: ChatThread, now: Any) -> ChatThread:
    thread.archived_at = now
    await db.flush()
    await db.refresh(thread)
    return thread


async def create_message(db: AsyncSession, **fields: Any) -> ChatMessage:
    message = ChatMessage(**fields)
    db.add(message)
    await db.flush()
    return message


async def update_message(db: AsyncSession, *, message: ChatMessage, **fields: Any) -> ChatMessage:
    for key, value in fields.items():
        setattr(message, key, value)
    await db.flush()
    await db.refresh(message)
    return message


async def list_messages_for_thread(
    db: AsyncSession, *, thread_id: uuid.UUID, limit: int, offset: int
) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_prior_messages_for_thread(
    db: AsyncSession, *, thread_id: uuid.UUID
) -> list[ChatMessage]:
    """Every existing turn (both USER and ASSISTANT rows) for one thread, oldest
    first -- consumed only by `services/copilot_context_builder.py`, which packs
    every one of these as a `ContextBlock(role="untrusted_user_content", ...)`. Never
    exposed to a route response directly (use `list_messages_for_thread` for that --
    same rows, same ordering, kept as two named entry points so their very different
    call sites/trust treatment can't be confused)."""
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_context_snapshot(db: AsyncSession, **fields: Any) -> ThreadContextSnapshot:
    snapshot = ThreadContextSnapshot(**fields)
    db.add(snapshot)
    await db.flush()
    return snapshot


async def list_thread_summaries(
    db: AsyncSession, *, thread_id: uuid.UUID, scope: ThreadScope
) -> list[ThreadSummary]:
    """Filters `thread_id` AND `scope` together -- never `thread_id` alone (see
    module docstring)."""
    stmt = (
        select(ThreadSummary)
        .where(ThreadSummary.thread_id == thread_id, ThreadSummary.scope == scope)
        .order_by(ThreadSummary.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_latest_checkin_analysis_for_workspace(
    db: AsyncSession, *, workspace_id: uuid.UUID
) -> CheckinAnalysis | None:
    """The most recently computed `CheckinAnalysis` for a workspace, across every
    `RelationshipCheckin` cycle -- `CheckinAnalysis.result_json` already only ever
    holds the aggregated gap/trend numbers both members may see, never a raw
    per-user `CheckinResponse.value` (see repositories/checkins.py module
    docstring), so this is safe to expose to the Copilot context builder directly."""
    stmt = (
        select(CheckinAnalysis)
        .join(RelationshipCheckin, RelationshipCheckin.id == CheckinAnalysis.checkin_id)
        .where(CheckinAnalysis.workspace_id == workspace_id)
        .order_by(CheckinAnalysis.computed_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


__all__ = [
    "archive_thread",
    "create_context_snapshot",
    "create_message",
    "create_thread",
    "get_latest_checkin_analysis_for_workspace",
    "get_private_thread_for_owner",
    "get_shared_thread_for_workspace",
    "get_thread_for_workspace",
    "list_messages_for_thread",
    "list_prior_messages_for_thread",
    "list_thread_summaries",
    "update_message",
]
