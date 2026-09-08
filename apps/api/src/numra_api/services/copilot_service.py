"""PR-V2-09 -- thread get-or-create, message persistence, and the synchronous
generation orchestration (context builder -> pipeline -> validation -> persisted
ASSISTANT `ChatMessage`) for `routes/copilot_threads.py`.

Route-layer discipline (specs/v2/copilot-grounding-spec.md): which of
`copilot_context_builder.build_shared_context`/`build_private_context` runs is
decided here from `thread.scope` read fresh from the DB via a literal, exhaustive
match -- never from a client-supplied scope parameter. IDOR gates (404, never 403)
happen before any context is ever assembled.
"""

from __future__ import annotations

import datetime as dt
import logging
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import ChatMessage, ChatThread
from numra_api.models.enums import ChatMessageRole, ChatMessageStatus, ThreadScope
from numra_api.repositories.copilot import (
    archive_thread,
    create_context_snapshot,
    create_message,
    create_thread,
    get_private_thread_for_owner,
    get_shared_thread_for_workspace,
    get_thread_for_workspace,
    list_messages_for_thread,
    update_message,
)
from numra_api.repositories.workspaces import get_workspace_member
from numra_api.services.copilot_context_builder import (
    BuiltCopilotContext,
    assert_shared_consent_precondition,
    build_private_context,
    build_shared_context,
)
from numra_api.services.errors import ApplicationError, NotFoundError, ThreadArchiveForbidden
from numra_interpretation.llm.errors import LLMProviderError
from numra_interpretation.llm.types import LLMProvider
from numra_relationship_interpretation.copilot_pipeline import (
    COPILOT_PROMPT_VERSION,
    generate_copilot_reply,
)
from numra_relationship_interpretation.errors import AnalysisGenerationError

logger = logging.getLogger("numra_api.copilot_service")

__all__ = [
    "archive_thread_route",
    "get_or_create_shared_thread",
    "get_or_create_private_thread",
    "get_thread_for_caller",
    "list_thread_messages",
    "list_threads_for_caller",
    "post_message",
]


async def get_or_create_shared_thread(
    db: AsyncSession, *, workspace_id: uuid.UUID, requester_user_id: uuid.UUID
) -> ChatThread:
    """Idempotent: any ACTIVE member may call this; a second call from either member
    returns the same thread (never a second row, never an `IntegrityError` surfaced
    to the client -- `uq_chat_threads_one_shared_per_workspace` is the DB-level
    backstop for a race between two concurrent first-calls)."""
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=requester_user_id)
    if member is None:
        raise NotFoundError(f"workspace {workspace_id} not found")

    existing = await get_shared_thread_for_workspace(db, workspace_id=workspace_id)
    if existing is not None:
        return existing
    try:
        return await create_thread(
            db,
            workspace_id=workspace_id,
            owner_user_id=None,
            scope=ThreadScope.RELATIONSHIP_SHARED,
        )
    except IntegrityError:
        # uq_chat_threads_one_shared_per_workspace -- the other member's concurrent
        # first-call won the race. Same translate-and-retry pattern as
        # checkin_service.py's first-submission race handling.
        await db.rollback()
        winner = await get_shared_thread_for_workspace(db, workspace_id=workspace_id)
        if winner is None:  # pragma: no cover -- should be unreachable
            raise
        return winner


async def get_or_create_private_thread(
    db: AsyncSession, *, workspace_id: uuid.UUID, requester_user_id: uuid.UUID
) -> ChatThread:
    """Idempotent, owner-scoped -- always the caller's own thread, never another
    member's (`owner_user_id=requester_user_id` is server-derived, never accepted
    from the client)."""
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=requester_user_id)
    if member is None:
        raise NotFoundError(f"workspace {workspace_id} not found")

    existing = await get_private_thread_for_owner(
        db, workspace_id=workspace_id, owner_user_id=requester_user_id
    )
    if existing is not None:
        return existing
    try:
        return await create_thread(
            db,
            workspace_id=workspace_id,
            owner_user_id=requester_user_id,
            scope=ThreadScope.RELATIONSHIP_PRIVATE,
        )
    except IntegrityError:
        # uq_chat_threads_one_private_per_owner -- a concurrent duplicate call from
        # the same caller (e.g. a double-click) won the race.
        await db.rollback()
        winner = await get_private_thread_for_owner(
            db, workspace_id=workspace_id, owner_user_id=requester_user_id
        )
        if winner is None:  # pragma: no cover -- should be unreachable
            raise
        return winner


async def list_threads_for_caller(
    db: AsyncSession, *, workspace_id: uuid.UUID, requester_user_id: uuid.UUID
) -> list[ChatThread]:
    """Only the SHARED thread (if any) and the caller's OWN PRIVATE thread (if
    any) -- built by query construction (two targeted lookups), never by fetching
    every thread and post-filtering (specs/v2/copilot-grounding-spec.md: the
    partner's PRIVATE thread must never even transiently be in this result)."""
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=requester_user_id)
    if member is None:
        raise NotFoundError(f"workspace {workspace_id} not found")

    threads: list[ChatThread] = []
    shared = await get_shared_thread_for_workspace(db, workspace_id=workspace_id)
    if shared is not None:
        threads.append(shared)
    private = await get_private_thread_for_owner(
        db, workspace_id=workspace_id, owner_user_id=requester_user_id
    )
    if private is not None:
        threads.append(private)
    return threads


async def get_thread_for_caller(
    db: AsyncSession, *, workspace_id: uuid.UUID, thread_id: uuid.UUID, requester_user_id: uuid.UUID
) -> ChatThread:
    """IDOR gate shared by every per-thread route: membership + (if PRIVATE)
    `owner_user_id == caller`, else `NotFoundError` (404, never 403) -- an attacker
    with a leaked/guessed thread id of the partner's PRIVATE thread gets the exact
    same response as a thread id that never existed."""
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=requester_user_id)
    if member is None:
        raise NotFoundError(f"workspace {workspace_id} not found")

    thread = await get_thread_for_workspace(db, thread_id=thread_id, workspace_id=workspace_id)
    if thread is None:
        raise NotFoundError(f"thread {thread_id} not found")
    if (
        thread.scope == ThreadScope.RELATIONSHIP_PRIVATE
        and thread.owner_user_id != requester_user_id
    ):
        raise NotFoundError(f"thread {thread_id} not found")
    return thread


async def list_thread_messages(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    thread_id: uuid.UUID,
    requester_user_id: uuid.UUID,
    limit: int,
    offset: int,
) -> list[ChatMessage]:
    thread = await get_thread_for_caller(
        db, workspace_id=workspace_id, thread_id=thread_id, requester_user_id=requester_user_id
    )
    return await list_messages_for_thread(db, thread_id=thread.id, limit=limit, offset=offset)


async def archive_thread_route(
    db: AsyncSession, *, workspace_id: uuid.UUID, thread_id: uuid.UUID, requester_user_id: uuid.UUID
) -> ChatThread:
    thread = await get_thread_for_caller(
        db, workspace_id=workspace_id, thread_id=thread_id, requester_user_id=requester_user_id
    )
    # RELATIONSHIP_PRIVATE: owner-only (membership alone is not enough -- the
    # partner is an ACTIVE member but must never archive the requester's private
    # thread). RELATIONSHIP_SHARED: any ACTIVE member, already guaranteed by the
    # IDOR gate in get_thread_for_caller above.
    if (
        thread.scope == ThreadScope.RELATIONSHIP_PRIVATE
        and thread.owner_user_id != requester_user_id
    ):
        raise ThreadArchiveForbidden(f"thread {thread_id} is not owned by the caller")
    return await archive_thread(db, thread=thread, now=dt.datetime.now(dt.UTC))


async def _build_context(
    db: AsyncSession,
    *,
    thread: ChatThread,
    workspace_id: uuid.UUID,
    requester_user_id: uuid.UUID,
    user_query: str,
) -> BuiltCopilotContext:
    """The one place `thread.scope` (read from the DB) decides which structurally
    separate builder function runs -- a literal, exhaustive match, never a
    client-supplied scope."""
    match thread.scope:
        case ThreadScope.RELATIONSHIP_SHARED:
            return await build_shared_context(
                db,
                workspace_id=workspace_id,
                requester_user_id=requester_user_id,
                thread=thread,
                user_query=user_query,
            )
        case ThreadScope.RELATIONSHIP_PRIVATE:
            return await build_private_context(
                db,
                workspace_id=workspace_id,
                requester_user_id=requester_user_id,
                thread=thread,
                user_query=user_query,
            )
        case ThreadScope.PERSONAL_PRIVATE:
            # PR-V2-09b, not implemented in this PR -- table/CHECK-constraint shape
            # exists (models/tables.py::ChatThread), but no route ever creates such
            # a thread here, so this branch should be unreachable in practice.
            raise NotFoundError(f"thread {thread.id} not found")


async def post_message(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    thread_id: uuid.UUID,
    requester_user_id: uuid.UUID,
    content: str,
    llm: LLMProvider,
) -> tuple[ChatMessage, ChatMessage]:
    """Persists the USER `ChatMessage` synchronously, then SYNCHRONOUSLY (no job/
    worker -- interactive chat latency) runs context-build -> pipeline -> validate
    and persists the ASSISTANT reply. On `LLMProviderError`/`AnalysisGenerationError`
    the ASSISTANT row is persisted as FAILED with an `error_code` -- this function
    still returns normally (the route returns 201): the USER message is saved and
    retry is possible, a transient/validation failure is never a 500."""
    thread = await get_thread_for_caller(
        db, workspace_id=workspace_id, thread_id=thread_id, requester_user_id=requester_user_id
    )

    # Consent-Gate, checked as an upfront precondition (same tier as the
    # ownership/scope gate above) for RELATIONSHIP_SHARED -- a missing mutual grant
    # raises ConsentNotGranted here and NOTHING is persisted (blueprint: "Gleiches
    # Ownership/Scope-Gate wie GET. Consent-Gate: SHARED->mutual..."). This is
    # deliberately distinct from the try/except below, which only covers failures
    # *during generation* (LLMProviderError et al.) that still persist a FAILED
    # ASSISTANT row and return 201 -- a missing consent precondition never gets that
    # far. RELATIONSHIP_PRIVATE has no equivalent upfront gate: every partner block
    # is gated individually, soft-fail, inside build_private_context.
    if thread.scope == ThreadScope.RELATIONSHIP_SHARED:
        await assert_shared_consent_precondition(
            db, workspace_id=workspace_id, requester_user_id=requester_user_id
        )

    user_message = await create_message(
        db,
        thread_id=thread.id,
        role=ChatMessageRole.USER,
        status=ChatMessageStatus.COMPLETE,
        author_user_id=requester_user_id,
        content=content,
    )

    assistant_message = await create_message(
        db,
        thread_id=thread.id,
        role=ChatMessageRole.ASSISTANT,
        status=ChatMessageStatus.GENERATING,
        author_user_id=None,
        content="",
    )

    try:
        built = await _build_context(
            db,
            thread=thread,
            workspace_id=workspace_id,
            requester_user_id=requester_user_id,
            user_query=content,
        )
        snapshot = await create_context_snapshot(
            db,
            thread_id=thread.id,
            requester_user_id=requester_user_id,
            scope=thread.scope,
            context_version=thread.context_version,
            context_blocks_json=built.context_blocks_json,
            consent_scopes_checked=built.consent_scopes_checked,
        )

        result = await generate_copilot_reply(
            request=built.request,
            llm=llm,
            knowledge_version=built.knowledge_version,
            grounding_profiles=built.grounding_profiles,
        )

        assistant_message = await update_message(
            db,
            message=assistant_message,
            status=ChatMessageStatus.COMPLETE,
            content=result.text,
            basis_type=result.basis_type,
            prompt_version=COPILOT_PROMPT_VERSION,
            knowledge_version=built.knowledge_version,
            context_snapshot_id=snapshot.id,
            model_provider=result.model_provider,
            model_name=result.model_name,
        )
    except AnalysisGenerationError as exc:
        assistant_message = await update_message(
            db,
            message=assistant_message,
            status=ChatMessageStatus.FAILED,
            error_code=f"ANALYSIS_GENERATION_ERROR: {exc}"[:80],
        )
    except LLMProviderError as exc:
        assistant_message = await update_message(
            db,
            message=assistant_message,
            status=ChatMessageStatus.FAILED,
            error_code=f"LLM_PROVIDER_ERROR: {exc}"[:80],
        )
    except ApplicationError as exc:
        # A consent gate (build_shared_context's mutual-consent requirement) or
        # similar domain error -- persisted onto the ASSISTANT row rather than
        # aborting the whole request, so the USER message stays saved (blueprint:
        # "trotzdem 201"). Never logs `content` (specs/v2/api-contract.md
        # Observability: chat text is never logged).
        logger.info("Copilot message generation blocked for thread %s: %s", thread.id, exc.code)
        assistant_message = await update_message(
            db, message=assistant_message, status=ChatMessageStatus.FAILED, error_code=exc.code
        )

    return user_message, assistant_message
