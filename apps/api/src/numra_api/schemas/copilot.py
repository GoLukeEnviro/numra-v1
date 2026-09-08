"""PR-V2-09 -- request/response shapes for
/v1/workspaces/{workspace_id}/copilot/threads*.
"""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field

from numra_api.models.enums import ChatMessageRole, ChatMessageStatus, ThreadScope


class ThreadCreateRequest(BaseModel):
    scope: ThreadScope = Field(
        description="RELATIONSHIP_SHARED or RELATIONSHIP_PRIVATE only -- "
        "PERSONAL_PRIVATE is rejected (PR-V2-09b, not implemented in this PR)."
    )


class ChatThreadOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID | None
    owner_user_id: uuid.UUID | None
    scope: ThreadScope
    context_version: int
    created_at: dt.datetime
    archived_at: dt.datetime | None

    model_config = {"from_attributes": True}


class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    role: ChatMessageRole
    status: ChatMessageStatus
    author_user_id: uuid.UUID | None
    content: str
    basis_type: str | None
    prompt_version: str | None
    knowledge_version: str | None
    context_snapshot_id: uuid.UUID | None
    model_provider: str | None
    model_name: str | None
    error_code: str | None
    created_at: dt.datetime

    model_config = {"from_attributes": True}


class MessagePairOut(BaseModel):
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut


__all__ = [
    "ChatMessageOut",
    "ChatThreadOut",
    "MessageCreateRequest",
    "MessagePairOut",
    "ThreadCreateRequest",
]
