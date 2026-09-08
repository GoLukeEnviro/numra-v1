"""PR-V2-08 -- request/response shapes for
/v1/workspaces/{workspace_id}/roadmaps* and .../roadmaps/{roadmap_id}/milestones*.
`RelationshipRoadmapPatchRequest.status` deliberately only accepts
ACCEPTED/ARCHIVED (see services/relationship_roadmap_service.py::
_PATCHABLE_ROADMAP_STATUSES) -- same pattern as `WorkspaceTaskPatchRequest`.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal

from pydantic import BaseModel, Field

from numra_api.models.enums import MilestoneStatus, MilestoneType, RoadmapStatus, RoadmapType


class RelationshipRoadmapCreateRequest(BaseModel):
    roadmap_type: RoadmapType
    title: str = Field(min_length=1, max_length=200)


class RelationshipRoadmapPatchRequest(BaseModel):
    """Every field optional; `model_fields_set` at the route means only fields
    the client actually sent are applied -- same pattern as
    `WorkspaceTaskPatchRequest`. `title`/`roadmap_type` are rejected once the
    roadmap is ARCHIVED (see services/relationship_roadmap_service.py)."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    roadmap_type: RoadmapType | None = None
    status: Literal[RoadmapStatus.ACCEPTED, RoadmapStatus.ARCHIVED] | None = None


class RelationshipRoadmapOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    roadmap_type: RoadmapType
    title: str
    status: RoadmapStatus
    proposer_user_id: uuid.UUID | None
    source_analysis_id: uuid.UUID | None
    prompt_version: str | None
    knowledge_version: str | None
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


class RoadmapMilestoneCreateRequest(BaseModel):
    milestone_type: MilestoneType
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    target_date: dt.date | None = None
    sequence: int = 0


class RoadmapMilestonePatchRequest(BaseModel):
    """Every field optional; `model_fields_set` at the route means only fields
    the client actually sent are applied. `status=COMPLETED` sets
    `completed_at` server-side (see services/relationship_roadmap_service.py) --
    no route can trigger this automatically or via an LLM."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    target_date: dt.date | None = None
    sequence: int | None = None
    status: MilestoneStatus | None = None


class RoadmapMilestoneOut(BaseModel):
    id: uuid.UUID
    roadmap_id: uuid.UUID
    milestone_type: MilestoneType
    title: str
    description: str | None
    target_date: dt.date | None
    sequence: int
    status: MilestoneStatus
    completed_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime

    model_config = {"from_attributes": True}


__all__ = [
    "RelationshipRoadmapCreateRequest",
    "RelationshipRoadmapOut",
    "RelationshipRoadmapPatchRequest",
    "RoadmapMilestoneCreateRequest",
    "RoadmapMilestoneOut",
    "RoadmapMilestonePatchRequest",
]
