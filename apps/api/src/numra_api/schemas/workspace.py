from __future__ import annotations

from pydantic import BaseModel

from numra_api.schemas.calculation import CalculationSummaryOut
from numra_api.schemas.person import PersonOut
from numra_api.schemas.private_reflection import PrivateReflectionSummaryOut
from numra_api.schemas.report import ReportSummaryOut


class WorkspaceReportsOut(BaseModel):
    total: int
    latest: ReportSummaryOut | None


class WorkspacePrivateReflectionsOut(BaseModel):
    total: int
    latest: PrivateReflectionSummaryOut | None


class WorkspacePrivateNotesOut(BaseModel):
    total: int


class WorkspacePersonalTasksOut(BaseModel):
    total: int
    active: int


class WorkspaceOverviewOut(BaseModel):
    """GET /v1/me/workspace -- a schlanker Index über die Personal-Workspace-
    Bereiche eines Person (Counts + jeweils neuestes Element), kein Mega-Payload.
    PROFILE/TIMING/REPORTS-Detaildaten bleiben bei den bestehenden Endpunkten
    (GET /v1/people/{id}, GET /v1/people/{id}/timing, GET /v1/people/{id}/
    daily-brief) -- hier nur ein Verweis + Zähler, siehe
    specs/v2/personal-workspace-spec.md."""

    person: PersonOut
    latest_calculation: CalculationSummaryOut | None
    reports: WorkspaceReportsOut
    private_reflections: WorkspacePrivateReflectionsOut
    private_notes: WorkspacePrivateNotesOut
    personal_tasks: WorkspacePersonalTasksOut
