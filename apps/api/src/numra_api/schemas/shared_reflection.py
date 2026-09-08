"""PR-V2-08 -- request/response shapes for
POST /v1/private-reflections/{reflection_id}/share and
/v1/workspaces/{workspace_id}/shared-reflections*. No PATCH request shape --
`SharedReflection` is immutable after creation (see
models/tables.py::SharedReflection)."""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel


class SharePrivateReflectionRequest(BaseModel):
    workspace_id: uuid.UUID


class SharedReflectionOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    author_user_id: uuid.UUID
    source_private_reflection_id: uuid.UUID | None
    entry_date: dt.date
    content: str
    shared_at: dt.datetime
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


__all__ = [
    "SharePrivateReflectionRequest",
    "SharedReflectionOut",
]
