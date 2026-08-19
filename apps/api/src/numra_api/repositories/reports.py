from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from numra_api.models import Report, ReportJob, ReportSection
from numra_api.models.enums import ReportJobStatus, ReportType

#: In-flight statuses a crashed worker may have left a job in — these are still
#: reclaimable once their lease expires, not just QUEUED (restart safety).
_RECLAIMABLE_STATUSES = (
    ReportJobStatus.QUEUED,
    ReportJobStatus.OUTLINE,
    ReportJobStatus.GENERATING,
    ReportJobStatus.VALIDATING,
    ReportJobStatus.ASSEMBLING,
)

MAX_ATTEMPTS = 3

#: Exponential backoff base for retryable failures: attempt 1 -> 30s, attempt 2 -> 60s,
#: attempt 3 -> 120s, ... (attempt_count is already post-increment when a failure is
#: handled, so this indexes from the attempt that just failed).
BACKOFF_BASE_SECONDS = 30


async def get_report_job_by_idempotency_key(
    db: AsyncSession, *, user_id: uuid.UUID, idempotency_key: str
) -> ReportJob | None:
    stmt = select(ReportJob).where(
        ReportJob.user_id == user_id, ReportJob.idempotency_key == idempotency_key
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_report_with_job(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    calculation_id: uuid.UUID,
    report_type: ReportType,
    calculation_version: str,
    knowledge_version: str,
    prompt_version: str,
    profile_snapshot: dict[str, Any],
    report_schema_version: str,
    idempotency_key: str | None,
) -> tuple[Report, ReportJob]:
    report = Report(
        user_id=user_id,
        calculation_id=calculation_id,
        report_type=report_type,
        calculation_version=calculation_version,
        knowledge_version=knowledge_version,
        prompt_version=prompt_version,
        profile_snapshot=profile_snapshot,
        report_schema_version=report_schema_version,
        status="PENDING",
    )
    db.add(report)
    await db.flush()

    job = ReportJob(
        report_id=report.id,
        user_id=user_id,
        status=ReportJobStatus.QUEUED,
        idempotency_key=idempotency_key,
    )
    db.add(job)
    await db.flush()
    return report, job


async def get_report_for_user(
    db: AsyncSession, *, report_id: uuid.UUID, user_id: uuid.UUID
) -> Report | None:
    stmt = (
        select(Report)
        .where(Report.id == report_id, Report.user_id == user_id)
        .options(selectinload(Report.jobs))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_report_job_for_user(
    db: AsyncSession, *, job_id: uuid.UUID, user_id: uuid.UUID
) -> ReportJob | None:
    stmt = select(ReportJob).where(ReportJob.id == job_id, ReportJob.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def claim_next_job(
    db: AsyncSession, *, now: dt.datetime, lease_seconds: int
) -> ReportJob | None:
    """Atomically claim the next runnable job using SELECT ... FOR UPDATE SKIP LOCKED,
    so multiple concurrent workers never process the same job. Reclaims jobs whose
    lease has expired (crashed worker) as well as fresh QUEUED jobs."""
    stmt = (
        select(ReportJob)
        .where(
            ReportJob.status.in_(_RECLAIMABLE_STATUSES),
            or_(ReportJob.lease_until.is_(None), ReportJob.lease_until < now),
            or_(ReportJob.next_attempt_at.is_(None), ReportJob.next_attempt_at <= now),
            ReportJob.attempt_count < MAX_ATTEMPTS,
        )
        .order_by(ReportJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        return None

    job.status = ReportJobStatus.OUTLINE
    job.locked_at = now
    job.lease_until = now + dt.timedelta(seconds=lease_seconds)
    job.next_attempt_at = None
    job.attempt_count += 1
    await db.flush()
    return job


async def mark_job_status(
    db: AsyncSession,
    *,
    job: ReportJob,
    status: ReportJobStatus,
    progress: int | None = None,
    error_code: str | None = None,
) -> None:
    job.status = status
    if progress is not None:
        job.progress = progress
    if error_code is not None:
        job.error_code = error_code
    if status in (ReportJobStatus.COMPLETE, ReportJobStatus.FAILED, ReportJobStatus.CANCELLED):
        job.lease_until = None
    await db.flush()


async def requeue_job_for_retry(
    db: AsyncSession, *, job: ReportJob, now: dt.datetime, error_code: str
) -> None:
    """A retryable failure occurred and the job still has attempts left: put it back in
    a reclaimable status (QUEUED) with exponential backoff, instead of FAILED — FAILED
    is a terminal status `claim_next_job` never reclaims, so marking a job FAILED here
    would silently prevent the retry that `attempt_count < MAX_ATTEMPTS` promises.
    ``job.attempt_count`` was already incremented by the `claim_next_job` call that
    handed this job to the caller, so it directly indexes the backoff schedule."""
    backoff_seconds = BACKOFF_BASE_SECONDS * (2 ** max(0, job.attempt_count - 1))
    job.status = ReportJobStatus.QUEUED
    job.progress = 0
    job.lease_until = None
    job.next_attempt_at = now + dt.timedelta(seconds=backoff_seconds)
    job.error_code = error_code[:80]
    job.last_error_at = now
    await db.flush()


async def fail_job_terminally(
    db: AsyncSession, *, job: ReportJob, now: dt.datetime, error_code: str
) -> None:
    """A non-retryable failure, or a retryable one with no attempts left: FAILED is
    terminal here, so `claim_next_job` will never pick this job up again."""
    job.status = ReportJobStatus.FAILED
    job.lease_until = None
    job.next_attempt_at = None
    job.error_code = error_code[:80]
    job.last_error_at = now
    await db.flush()


async def persist_report_sections(
    db: AsyncSession, *, report: Report, sections: list[dict[str, Any]]
) -> None:
    for section in sections:
        db.add(
            ReportSection(
                report_id=report.id,
                section_id=section["section_id"],
                title=section["title"],
                order_index=section["order_index"],
                content_json=section,
                word_count=section["word_count"],
            )
        )
    await db.flush()


async def finalize_report(
    db: AsyncSession, *, report: Report, content_json: dict[str, Any], generated_at: dt.datetime
) -> None:
    report.status = "COMPLETE"
    report.content_json = content_json
    report.generated_at = generated_at
    await db.flush()


async def fail_report(db: AsyncSession, *, report: Report) -> None:
    report.status = "FAILED"
    await db.flush()
