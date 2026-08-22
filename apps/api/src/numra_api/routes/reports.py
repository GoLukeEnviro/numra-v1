from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, rate_limit_by_user, require_csrf
from numra_api.models import Person, Report, ReportJob, User
from numra_api.repositories.reports import (
    get_report_for_user,
    get_report_job_for_user,
    list_reports_for_user,
)
from numra_api.schemas.person_ref import PersonRefOut, person_display_name
from numra_api.schemas.report import (
    ReportCreateRequest,
    ReportJobOut,
    ReportOut,
    ReportSummaryOut,
)
from numra_api.services.errors import NotFoundError
from numra_api.services.report_service import create_report_job

router = APIRouter(prefix="/v1", tags=["reports"])


def _report_to_out(report: Report, job_id: uuid.UUID) -> ReportOut:
    return ReportOut(
        id=str(report.id),
        calculation_id=str(report.calculation_id),
        report_type=report.report_type,
        status=report.status,
        calculation_version=report.calculation_version,
        knowledge_version=report.knowledge_version,
        prompt_version=report.prompt_version,
        content=report.content_json,
        generated_at=report.generated_at,
        created_at=report.created_at,
        job_id=str(job_id),
    )


def _report_to_summary(report: Report, person: Person, word_count: int) -> ReportSummaryOut:
    return ReportSummaryOut(
        id=str(report.id),
        calculation_id=str(report.calculation_id),
        person=PersonRefOut(
            id=person.id,
            display_name=person_display_name(
                preferred_name=person.preferred_name,
                birth_first_names=person.birth_first_names,
                birth_last_name=person.birth_last_name,
            ),
        ),
        report_type=report.report_type,
        status=report.status,
        word_count=word_count,
        generated_at=report.generated_at,
        created_at=report.created_at,
    )


def _job_to_out(job: ReportJob) -> ReportJobOut:
    return ReportJobOut(
        id=str(job.id),
        report_id=str(job.report_id),
        status=job.status,
        progress=job.progress,
        attempt_count=job.attempt_count,
        error_code=job.error_code,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post(
    "/reports",
    response_model=ReportOut,
    status_code=201,
    dependencies=[
        Depends(require_csrf),
        Depends(rate_limit_by_user("reports:create", limit=30, window_seconds=3600)),
    ],
)
async def create_report_route(
    body: ReportCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ReportOut:
    report, job = await create_report_job(
        db,
        user_id=user.id,
        calculation_id=uuid.UUID(body.calculation_id),
        report_type=body.report_type,
        idempotency_key=idempotency_key,
    )
    return _report_to_out(report, job.id)


@router.get("/reports", response_model=list[ReportSummaryOut])
async def list_reports_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    person_id: uuid.UUID | None = Query(default=None),
    calculation_id: uuid.UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ReportSummaryOut]:
    rows = await list_reports_for_user(
        db,
        user_id=user.id,
        person_id=person_id,
        calculation_id=calculation_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return [_report_to_summary(report, person, word_count) for report, person, word_count in rows]


@router.get("/reports/{report_id}", response_model=ReportOut)
async def get_report_route(
    report_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportOut:
    report = await get_report_for_user(db, report_id=report_id, user_id=user.id)
    if report is None:
        raise NotFoundError(f"report {report_id} not found")
    job_id = report.jobs[0].id if report.jobs else report.id
    return _report_to_out(report, job_id)


@router.get("/report-jobs/{job_id}", response_model=ReportJobOut)
async def get_report_job_route(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportJobOut:
    job = await get_report_job_for_user(db, job_id=job_id, user_id=user.id)
    if job is None:
        raise NotFoundError(f"report job {job_id} not found")
    return _job_to_out(job)
