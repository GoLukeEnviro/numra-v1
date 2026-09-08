"""PR-V2-06 -- request/response shapes for /v1/workspaces/{workspace_id}/checkin*.

Privacy (specs/v2/checkin-spec.md Section 19): `CheckinOut.my_responses` is always
the CALLER's own values only (services/checkin_service.py::get_checkin /
submit_checkin already scope the query to `user_id`). There is deliberately no field
anywhere in this module for a partner's raw value -- not even as a nullable
placeholder whose name would leak that such a value exists.
"""

from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field

from numra_api.models.enums import CheckinStatus


class CheckinDimensionOut(BaseModel):
    id: uuid.UUID
    semantic_key: str
    label: str
    description: str | None
    scale_min: int
    scale_max: int
    sort_order: int
    active: bool
    retired_at: dt.datetime | None

    model_config = {"from_attributes": True}


class CheckinTemplateOut(BaseModel):
    id: uuid.UUID
    version: int
    active: bool
    dimensions: list[CheckinDimensionOut]


class CheckinDimensionCreateRequest(BaseModel):
    semantic_key: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    scale_min: int = Field(default=1, ge=0)
    scale_max: int = Field(default=10, le=100)
    sort_order: int = Field(default=0)


class CheckinDimensionUpdateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    active: bool | None = None


class CheckinResponseIn(BaseModel):
    dimension_id: uuid.UUID
    value: int


class CheckinSubmitRequest(BaseModel):
    responses: list[CheckinResponseIn] = Field(min_length=1)


class CheckinResponseOut(BaseModel):
    """Always the CALLER's own submitted value -- see module docstring."""

    dimension_id: uuid.UUID
    semantic_key: str
    value: int
    submitted_at: dt.datetime

    model_config = {"from_attributes": True}


class DimensionAnalysisOut(BaseModel):
    absolute_gap: int
    direction: str
    rolling_trend: float
    sample_size: int
    historical_delta: float | None
    sufficient_evidence: bool


class CheckinAnalysisOut(BaseModel):
    computed_at: dt.datetime
    result: dict[str, DimensionAnalysisOut]


class CheckinOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    checkin_template_version: int
    status: CheckinStatus
    cycle_started_at: dt.datetime
    my_responses: list[CheckinResponseOut]
    analysis: CheckinAnalysisOut | None


class CheckinSummaryOut(BaseModel):
    id: uuid.UUID
    checkin_template_version: int
    status: CheckinStatus
    cycle_started_at: dt.datetime

    model_config = {"from_attributes": True}


__all__ = [
    "CheckinAnalysisOut",
    "CheckinDimensionCreateRequest",
    "CheckinDimensionOut",
    "CheckinDimensionUpdateRequest",
    "CheckinOut",
    "CheckinResponseIn",
    "CheckinResponseOut",
    "CheckinSubmitRequest",
    "CheckinSummaryOut",
    "CheckinTemplateOut",
    "DimensionAnalysisOut",
]
