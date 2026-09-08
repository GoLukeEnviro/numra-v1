from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from pydantic import BaseModel

from numra_api.models.enums import AnalysisJobStatus, AnalysisType


class AnalysisJobOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    analysis_type: AnalysisType
    status: AnalysisJobStatus
    progress: int
    attempt_count: int
    error_code: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class RelationshipAnalysisOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    job_id: uuid.UUID
    relationship_type: str
    calculation_version: str
    knowledge_version: str
    prompt_version: str
    model_provider: str | None
    model_name: str | None
    status: str
    result: dict[str, Any] | None
    generated_at: dt.datetime | None
    created_at: dt.datetime


class ShadowDynamicsAnalysisOut(BaseModel):
    id: uuid.UUID
    workspace_id: uuid.UUID
    job_id: uuid.UUID
    relationship_type: str
    calculation_version: str
    knowledge_version: str
    prompt_version: str
    model_provider: str | None
    model_name: str | None
    status: str
    result: dict[str, Any] | None
    generated_at: dt.datetime | None
    created_at: dt.datetime
