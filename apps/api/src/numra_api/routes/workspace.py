from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db
from numra_api.models import User
from numra_api.repositories.people import get_person
from numra_api.repositories.workspace import get_workspace_overview
from numra_api.schemas.calculation import CalculationSummaryOut
from numra_api.schemas.person import PersonOut
from numra_api.schemas.person_ref import PersonRefOut, person_display_name
from numra_api.schemas.private_reflection import PrivateReflectionSummaryOut
from numra_api.schemas.report import ReportSummaryOut
from numra_api.schemas.workspace import (
    WorkspaceOverviewOut,
    WorkspacePersonalTasksOut,
    WorkspacePrivateNotesOut,
    WorkspacePrivateReflectionsOut,
    WorkspaceReportsOut,
)
from numra_api.services.errors import NotFoundError

router = APIRouter(prefix="/v1/me", tags=["workspace"])


@router.get("/workspace", response_model=WorkspaceOverviewOut)
async def get_my_workspace_route(
    person_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceOverviewOut:
    """Schlanker Index über den Personal Workspace einer Person -- Counts +
    jeweils neuestes Element pro Bereich, kein Mega-Payload. PROFILE/TIMING/
    REPORTS-Details bleiben bei den bestehenden Endpunkten (GET /v1/people/
    {person_id}, .../timing, .../daily-brief) -- die werden hier nicht erneut
    eingebettet. `person_id` ist Pflicht-Query-Parameter, kein impliziter
    Self-Default (specs/v2/personal-workspace-spec.md)."""
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")

    overview = await get_workspace_overview(db, person=person, user_id=user.id)

    latest_report_out: ReportSummaryOut | None = None
    if overview.latest_report is not None and overview.latest_report_person is not None:
        report = overview.latest_report
        report_person = overview.latest_report_person
        latest_report_out = ReportSummaryOut(
            id=str(report.id),
            calculation_id=str(report.calculation_id),
            person=PersonRefOut(
                id=report_person.id,
                display_name=person_display_name(
                    preferred_name=report_person.preferred_name,
                    birth_first_names=report_person.birth_first_names,
                    birth_last_name=report_person.birth_last_name,
                ),
            ),
            report_type=report.report_type,
            status=report.status,
            word_count=overview.latest_report_word_count,
            generated_at=report.generated_at,
            created_at=report.created_at,
        )

    latest_reflection_out: PrivateReflectionSummaryOut | None = None
    if overview.latest_reflection is not None:
        latest_reflection_out = PrivateReflectionSummaryOut.model_validate(
            overview.latest_reflection, from_attributes=True
        )

    return WorkspaceOverviewOut(
        person=PersonOut.model_validate(overview.person, from_attributes=True),
        latest_calculation=(
            CalculationSummaryOut(
                id=str(overview.latest_calculation.id),
                person_id=str(overview.latest_calculation.person_id),
                as_of_date=overview.latest_calculation.as_of_date,
                calculation_version=overview.latest_calculation.calculation_version,
                schema_version=overview.latest_calculation.schema_version,
                deterministic_hash=overview.latest_calculation.deterministic_hash,
                created_at=overview.latest_calculation.created_at,
            )
            if overview.latest_calculation is not None
            else None
        ),
        reports=WorkspaceReportsOut(total=overview.reports_total, latest=latest_report_out),
        private_reflections=WorkspacePrivateReflectionsOut(
            total=overview.reflections_total, latest=latest_reflection_out
        ),
        private_notes=WorkspacePrivateNotesOut(total=overview.notes_total),
        personal_tasks=WorkspacePersonalTasksOut(
            total=overview.tasks_total, active=overview.tasks_active
        ),
    )
