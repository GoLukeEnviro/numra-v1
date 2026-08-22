from __future__ import annotations

import datetime as dt
from typing import Any

from pydantic import BaseModel

from numra_api.models.enums import ReportJobStatus, ReportType
from numra_api.schemas.person_ref import PersonRefOut


class ReportCreateRequest(BaseModel):
    calculation_id: str
    report_type: ReportType


class ReportOut(BaseModel):
    id: str
    calculation_id: str
    report_type: ReportType
    status: str
    calculation_version: str
    knowledge_version: str
    prompt_version: str
    content: dict[str, Any] | None
    generated_at: dt.datetime | None
    created_at: dt.datetime
    job_id: str


class ReportSummaryOut(BaseModel):
    """Report-library list shape: a resolved person reference and a computed
    word_count instead of the full `content` payload, which a list card never
    renders."""

    id: str
    calculation_id: str
    person: PersonRefOut
    report_type: ReportType
    status: str
    word_count: int
    generated_at: dt.datetime | None
    created_at: dt.datetime


class ReportJobOut(BaseModel):
    id: str
    report_id: str
    status: ReportJobStatus
    progress: int
    attempt_count: int
    error_code: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
