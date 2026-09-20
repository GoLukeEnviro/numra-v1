"""PWA-06 / #123 -- the personal (workspace-free) Copilot surface.

`routes/copilot_threads.py` is bound to `/v1/workspaces/{workspace_id}/copilot`, and
every one of its routes needs a workspace and an ACTIVE membership. A personal thread
is `scope=PERSONAL_PRIVATE` with `workspace_id IS NULL` (specs/v2/
personal-workspace-spec.md lists `PRIVATE COPILOT` as a personal surface; specs/v2/
copilot-grounding-spec.md freezes the shape), so it can never be reached -- and must
never be reachable -- through a workspace path. This router is that disjoint second
gate family: `owner_user_id` comes from the authenticated caller, never from the
client.

IDOR discipline (specs/v2/privacy-spec.md Section 49), identical to the workspace
routes: a thread id that does not exist, belongs to another user, or is a
relationship thread yields **404, never 403** -- a leaked/guessed id must be
indistinguishable from a nonexistent one. Unauthenticated calls yield 401 as on every
other `/v1` route.

Feature flag: `require_v2_phase("copilot")` -- the same finer-grained dependency the
workspace Copilot router uses (not `require_v2_master()` alone), so flag behaviour is
identical across both Copilot surfaces.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import (
    get_current_user,
    get_db,
    get_llm_provider,
    rate_limit_by_user,
    require_csrf,
)
from numra_api.models import ChatMessage, ChatThread, User
from numra_api.models.enums import ThreadScope
from numra_api.schemas.copilot import (
    ChatMessageOut,
    ChatThreadOut,
    MessageCreateRequest,
    MessagePairOut,
    PersonalThreadCreateRequest,
)
from numra_api.services.copilot_service import (
    archive_personal_thread_route,
    get_or_create_personal_thread,
    get_personal_thread_for_caller,
    list_personal_thread_messages,
    list_personal_threads_for_caller,
    post_personal_message,
)
from numra_api.services.errors import ApplicationError
from numra_api.services.feature_flags import require_v2_phase
from numra_interpretation.llm.types import LLMProvider

router = APIRouter(
    prefix="/v1/me/copilot",
    tags=["personal-copilot"],
    dependencies=[Depends(require_v2_phase("copilot"))],
)


class _UnsupportedPersonalThreadScope(ApplicationError):
    """A personal thread is always PERSONAL_PRIVATE -- an explicit other scope is a
    client error (422), never silently coerced into the personal scope."""

    code = "UNSUPPORTED_THREAD_SCOPE"
    status_code = 422


def _thread_out(thread: ChatThread) -> ChatThreadOut:
    return ChatThreadOut.model_validate(thread, from_attributes=True)


def _message_out(message: ChatMessage) -> ChatMessageOut:
    return ChatMessageOut.model_validate(message, from_attributes=True)


@router.post(
    "/threads",
    response_model=ChatThreadOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def create_personal_thread_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
    body: PersonalThreadCreateRequest | None = None,
) -> ChatThreadOut:
    """Get-or-create the caller's own personal thread -- idempotent, at most one
    non-archived personal thread per owner (DB-enforced by
    `uq_chat_threads_one_personal_per_owner`). No workspace and no membership are
    involved: the personal Copilot works for a user with no connection at all."""
    if body is not None and body.scope is not None and body.scope != ThreadScope.PERSONAL_PRIVATE:
        raise _UnsupportedPersonalThreadScope(
            f"scope={body.scope!r} is not creatable via this route -- it creates the "
            "caller's PERSONAL_PRIVATE thread only"
        )
    thread = await get_or_create_personal_thread(db, requester_user_id=user.id)
    return _thread_out(thread)


@router.get("/threads", response_model=list[ChatThreadOut])
async def list_personal_threads_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> list[ChatThreadOut]:
    threads = await list_personal_threads_for_caller(db, requester_user_id=user.id)
    return [_thread_out(t) for t in threads]


@router.get("/threads/{thread_id}", response_model=ChatThreadOut)
async def get_personal_thread_route(
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> ChatThreadOut:
    thread = await get_personal_thread_for_caller(
        db, thread_id=thread_id, requester_user_id=user.id
    )
    return _thread_out(thread)


@router.get("/threads/{thread_id}/messages", response_model=list[ChatMessageOut])
async def list_personal_messages_route(
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ChatMessageOut]:
    messages = await list_personal_thread_messages(
        db,
        thread_id=thread_id,
        requester_user_id=user.id,
        limit=limit,
        offset=offset,
    )
    return [_message_out(m) for m in messages]


@router.post(
    "/threads/{thread_id}/messages",
    response_model=MessagePairOut,
    status_code=201,
    dependencies=[
        Depends(require_csrf),
        Depends(rate_limit_by_user("copilot:message", limit=30, window_seconds=3600)),
    ],
)
async def post_personal_message_route(
    thread_id: uuid.UUID,
    body: MessageCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
    llm: LLMProvider = Depends(get_llm_provider),
) -> MessagePairOut:
    user_message, assistant_message = await post_personal_message(
        db,
        thread_id=thread_id,
        requester_user_id=user.id,
        content=body.content,
        llm=llm,
    )
    return MessagePairOut(
        user_message=_message_out(user_message), assistant_message=_message_out(assistant_message)
    )


@router.post(
    "/threads/{thread_id}/archive",
    response_model=ChatThreadOut,
    dependencies=[Depends(require_csrf)],
)
async def archive_personal_thread_route_handler(
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> ChatThreadOut:
    thread = await archive_personal_thread_route(db, thread_id=thread_id, requester_user_id=user.id)
    return _thread_out(thread)
