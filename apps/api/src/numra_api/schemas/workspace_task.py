"""PR-V2-07 -- request/response shapes for
/v1/workspaces/{workspace_id}/tasks*. `WorkspaceTaskPatchRequest.status`
deliberately only accepts COMPLETED/ARCHIVED (see
services/workspace_task_service.py::_PATCHABLE_STATUSES) -- PROPOSED/ACCEPTED/
ACTIVE transitions are exclusively driven by the accept/decline endpoints.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from numra_api.models.enums import TaskType, WorkspaceTaskStatus


class WorkspaceTaskCreateRequest(BaseModel):
    task_type: TaskType
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    due_date: dt.date | None = None
    #: Only meaningful for FOR_PARTNER_PROPOSED -- used solely to validate the
    #: caller's expectation against the true (membership-derived) recipient, see
    #: services/workspace_task_service.py::create_task.
    recipient_user_id: uuid.UUID | None = None
    #: PR-V2-08 -- optional link into the Roadmap system. Must reference a
    #: `RoadmapMilestone` belonging to the same workspace (validated server-side,
    #: see services/workspace_task_service.py::create_task).
    roadmap_milestone_id: uuid.UUID | None = None


class WorkspaceTaskPatchRequest(BaseModel):
    """Every field optional; `model_fields_set` at the route means only fields
    the client actually sent are applied -- same pattern as
    `PersonalTaskPatchRequest`."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    due_date: dt.date | None = None
    status: Literal[WorkspaceTaskStatus.COMPLETED, WorkspaceTaskStatus.ARCHIVED] | None = None
    #: PR-V2-08 -- set/clear the Roadmap-Milestone link; `None` clears it. Setting
    #: a non-`None` value is validated against the task's workspace (see
    #: services/workspace_task_service.py::patch_task).
    roadmap_milestone_id: uuid.UUID | None = None


class WorkspaceTaskOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    task_type: TaskType
    status: WorkspaceTaskStatus
    proposer_user_id: uuid.UUID | None
    recipient_user_id: uuid.UUID | None
    title: str
    description: str | None
    due_date: dt.date | None
    completed_at: dt.datetime | None
    source_analysis_id: uuid.UUID | None
    prompt_version: str | None
    knowledge_version: str | None
    roadmap_milestone_id: uuid.UUID | None
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


__all__ = [
    "WorkspaceTaskCreateRequest",
    "WorkspaceTaskOut",
    "WorkspaceTaskPatchRequest",
]
