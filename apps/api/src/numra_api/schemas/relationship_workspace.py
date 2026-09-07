"""GET/PATCH /v1/workspaces/{workspace_id} + GET /v1/workspaces -- OVERVIEW (pure
metadata grid) + DUAL PROFILE (pure canon-number side-by-side, no interpretation).
COMMUNICATION/CLOSENESS/AUTONOMY/NEEDS/STRENGTHS/CONFLICT DYNAMICS and every other
LLM-interpreted section from specs/v2/relationship-workspace-spec.md are
deliberately absent here -- PR-V2-05.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel

from numra_api.models.enums import RelationshipType, WorkspaceStatus
from numra_api.schemas.person_ref import PersonRefOut


class WorkspaceUpdateRequest(BaseModel):
    relationship_type: RelationshipType


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    status: WorkspaceStatus
    relationship_type: RelationshipType | None
    created_at: dt.datetime
    dissolved_at: dt.datetime | None

    model_config = {"from_attributes": True}


class DualProfileMemberOut(BaseModel):
    """One member's side of the DUAL PROFILE grid. `self_person`/`core_numbers` are
    both `None` when the member has never created a SELF-mode Person yet, or when
    the viewer lacks an active CORE_NUMEROLOGY consent grant from this member
    (services/relationship_workspace_service.py::_build_dual_profile_member) -- never
    a 403/500 for either case, the response degrades gracefully per-side."""

    user_id: uuid.UUID
    display_name: str
    self_person: PersonRefOut | None
    core_numbers: dict[str, Any] | None


class WorkspaceOverviewOut(BaseModel):
    workspace: WorkspaceOut
    dual_profile: list[DualProfileMemberOut]


class WorkspaceSummaryOut(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    status: WorkspaceStatus
    relationship_type: RelationshipType | None
    created_at: dt.datetime
    dissolved_at: dt.datetime | None

    model_config = {"from_attributes": True}
