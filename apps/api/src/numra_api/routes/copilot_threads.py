"""PR-V2-09 -- specs/v2/copilot-grounding-spec.md, specs/v2/api-contract.md. Every
route gates on membership first (404, never 403, for a non-member -- same IDOR
discipline as routes/relationship_roadmaps.py); per-thread routes additionally gate
RELATIONSHIP_PRIVATE ownership the same way (`services/copilot_service.py::
get_thread_for_caller`). `scope` is only ever accepted on `POST .../threads`
(create) -- every other route reads it back from the persisted `ChatThread`, it is
never trusted from the client again afterwards."""

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
    ThreadCreateRequest,
)
from numra_api.services.copilot_service import (
    archive_thread_route,
    get_or_create_private_thread,
    get_or_create_shared_thread,
    get_thread_for_caller,
    list_thread_messages,
    list_threads_for_caller,
    post_message,
)
from numra_api.services.errors import ApplicationError
from numra_interpretation.llm.types import LLMProvider

router = APIRouter(prefix="/v1/workspaces/{workspace_id}/copilot", tags=["copilot"])


class _UnsupportedThreadScope(ApplicationError):
    """PERSONAL_PRIVATE is not creatable via this route (PR-V2-09b, not implemented
    in this PR -- see specs/v2/copilot-grounding-spec.md scope note in the module
    docstring of `services/copilot_context_builder.py`)."""

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
async def create_thread_route(
    workspace_id: uuid.UUID,
    body: ThreadCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatThreadOut:
    if body.scope == ThreadScope.RELATIONSHIP_SHARED:
        thread = await get_or_create_shared_thread(
            db, workspace_id=workspace_id, requester_user_id=user.id
        )
    elif body.scope == ThreadScope.RELATIONSHIP_PRIVATE:
        thread = await get_or_create_private_thread(
            db, workspace_id=workspace_id, requester_user_id=user.id
        )
    else:
        raise _UnsupportedThreadScope(
            f"scope={body.scope!r} is not creatable via this route (PR-V2-09b)"
        )
    return _thread_out(thread)


@router.get("/threads", response_model=list[ChatThreadOut])
async def list_threads_route(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ChatThreadOut]:
    threads = await list_threads_for_caller(
        db, workspace_id=workspace_id, requester_user_id=user.id
    )
    return [_thread_out(t) for t in threads]


@router.get("/threads/{thread_id}", response_model=ChatThreadOut)
async def get_thread_route(
    workspace_id: uuid.UUID,
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatThreadOut:
    thread = await get_thread_for_caller(
        db, workspace_id=workspace_id, thread_id=thread_id, requester_user_id=user.id
    )
    return _thread_out(thread)


@router.get("/threads/{thread_id}/messages", response_model=list[ChatMessageOut])
async def list_messages_route(
    workspace_id: uuid.UUID,
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ChatMessageOut]:
    messages = await list_thread_messages(
        db,
        workspace_id=workspace_id,
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
async def post_message_route(
    workspace_id: uuid.UUID,
    thread_id: uuid.UUID,
    body: MessageCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: LLMProvider = Depends(get_llm_provider),
) -> MessagePairOut:
    user_message, assistant_message = await post_message(
        db,
        workspace_id=workspace_id,
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
async def archive_thread_route_handler(
    workspace_id: uuid.UUID,
    thread_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatThreadOut:
    thread = await archive_thread_route(
        db, workspace_id=workspace_id, thread_id=thread_id, requester_user_id=user.id
    )
    return _thread_out(thread)
