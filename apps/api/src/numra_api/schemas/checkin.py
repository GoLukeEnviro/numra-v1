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
from typing import Literal

from pydantic import BaseModel, Field, StrictInt

from numra_api.models.enums import CheckinStatus


class CheckinValidationIssueOut(BaseModel):
    loc: list[str | int]
    type: str


class CheckinErrorOut(BaseModel):
    code: str
    message: str
    detail: list[CheckinValidationIssueOut] | None = None


class CheckinDimensionOut(BaseModel):
    id: uuid.UUID
    semantic_key: str
    label: str
    description: str | None
    scale_min: int
    scale_max: int
    sort_order: int
    dimension_class: Literal["INTIMATE"] | None
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
    dimension_class: Literal["INTIMATE"] | None = None


class CheckinDimensionUpdateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    active: bool | None = None


class CheckinRoundStartRequest(BaseModel):
    """Optional empty object only; no ignored round-start parameters."""

    model_config = {"extra": "forbid"}


class CheckinResponseIn(BaseModel):
    model_config = {"extra": "forbid"}

    dimension_id: uuid.UUID
    value: StrictInt


class CheckinSubmitRequest(BaseModel):
    model_config = {"extra": "forbid"}

    round_id: uuid.UUID
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


class CheckinRoundDimensionOut(BaseModel):
    dimension_id: uuid.UUID
    semantic_key: str
    label: str
    description: str | None
    scale_min: int
    scale_max: int
    sort_order: int

    model_config = {"from_attributes": True}


class CheckinRoundOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    checkin_template_version: int
    status: CheckinStatus
    cycle_started_at: dt.datetime
    snapshot_origin: Literal["ROUND_START", "MIGRATION_CURRENT", "LEGACY_MISSING"]
    snapshot_recorded: bool
    dimensions: list[CheckinRoundDimensionOut]


class CheckinOut(CheckinRoundOut):
    my_responses: list[CheckinResponseOut]
    partner_submitted: bool
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
