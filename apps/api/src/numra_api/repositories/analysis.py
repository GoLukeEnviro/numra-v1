"""Repository for `AnalysisJob`/`RelationshipAnalysis`/`ShadowDynamicsAnalysis` (PR-V2-05).

Same patterns as `repositories/reports.py`: `claim_next_analysis_job` uses
``SELECT ... FOR UPDATE SKIP LOCKED`` so multiple worker processes never double-process
a job, and `get_analysis_job_for_user` is the IDOR gate for the polling route.
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import (
    AnalysisJob,
    RelationshipAnalysis,
    ShadowDynamicsAnalysis,
    WorkspaceMember,
)
from numra_api.models.enums import AnalysisJobStatus, AnalysisType, WorkspaceMemberStatus

#: Same rationale as `repositories.reports._RECLAIMABLE_STATUSES` -- crashed-worker
#: recovery via lease expiry, not just fresh QUEUED jobs.
_RECLAIMABLE_STATUSES = (
    AnalysisJobStatus.QUEUED,
    AnalysisJobStatus.GENERATING,
    AnalysisJobStatus.VALIDATING,
)

#: Kept identical to `repositories.reports.MAX_ATTEMPTS` -- same retry budget rationale.
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 30


async def get_analysis_job_by_idempotency_key(
    db: AsyncSession, *, user_id: uuid.UUID, idempotency_key: str
) -> AnalysisJob | None:
    stmt = select(AnalysisJob).where(
        AnalysisJob.requested_by_user_id == user_id, AnalysisJob.idempotency_key == idempotency_key
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_analysis_job(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
    analysis_type: AnalysisType,
    idempotency_key: str | None,
) -> AnalysisJob:
    job = AnalysisJob(
        workspace_id=workspace_id,
        requested_by_user_id=requested_by_user_id,
        analysis_type=analysis_type,
        status=AnalysisJobStatus.QUEUED,
        idempotency_key=idempotency_key,
    )
    db.add(job)
    await db.flush()
    return job


async def get_analysis_job_by_id(db: AsyncSession, *, job_id: uuid.UUID) -> AnalysisJob | None:
    return await db.get(AnalysisJob, job_id)


async def get_analysis_job_for_user(
    db: AsyncSession, *, job_id: uuid.UUID, user_id: uuid.UUID
) -> AnalysisJob | None:
    """IDOR gate for `GET /v1/analysis-jobs/{job_id}`: readable by any ACTIVE member of
    the job's workspace, not only the original requester -- a relationship/shadow
    analysis is a shared, two-person result (specs/v2/shadow-dynamics-spec.md), unlike
    a personal `Report` which is single-owner (`repositories.reports.get_report_job_for_user`
    filters on `user_id` alone for that reason)."""
    stmt = (
        select(AnalysisJob)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == AnalysisJob.workspace_id)
        .where(
            AnalysisJob.id == job_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def claim_next_analysis_job(
    db: AsyncSession, *, now: dt.datetime, lease_seconds: int
) -> AnalysisJob | None:
    """Atomically claim the next runnable job -- exact `claim_next_job` pattern from
    `repositories.reports`, applied to `analysis_jobs`."""
    stmt = (
        select(AnalysisJob)
        .where(
            AnalysisJob.status.in_(_RECLAIMABLE_STATUSES),
            or_(AnalysisJob.lease_until.is_(None), AnalysisJob.lease_until < now),
            or_(AnalysisJob.next_attempt_at.is_(None), AnalysisJob.next_attempt_at <= now),
            AnalysisJob.attempt_count < MAX_ATTEMPTS,
        )
        .order_by(AnalysisJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        return None

    job.status = AnalysisJobStatus.GENERATING
    job.locked_at = now
    job.lease_until = now + dt.timedelta(seconds=lease_seconds)
    job.next_attempt_at = None
    job.attempt_count += 1
    await db.flush()
    return job


async def mark_job_status(
    db: AsyncSession,
    *,
    job: AnalysisJob,
    status: AnalysisJobStatus,
    progress: int | None = None,
    error_code: str | None = None,
) -> None:
    job.status = status
    if progress is not None:
        job.progress = progress
    if error_code is not None:
        job.error_code = error_code
    if status in (AnalysisJobStatus.COMPLETE, AnalysisJobStatus.FAILED):
        job.lease_until = None
    await db.flush()


async def requeue_job_for_retry(
    db: AsyncSession, *, job: AnalysisJob, now: dt.datetime, error_code: str
) -> None:
    """Same exponential-backoff-then-requeue pattern as
    `repositories.reports.requeue_job_for_retry` -- see that function's docstring."""
    backoff_seconds = BACKOFF_BASE_SECONDS * (2 ** max(0, job.attempt_count - 1))
    job.status = AnalysisJobStatus.QUEUED
    job.progress = 0
    job.lease_until = None
    job.next_attempt_at = now + dt.timedelta(seconds=backoff_seconds)
    job.error_code = error_code[:60]
    job.last_error_at = now
    await db.flush()


async def fail_job_terminally(
    db: AsyncSession, *, job: AnalysisJob, now: dt.datetime, error_code: str
) -> None:
    job.status = AnalysisJobStatus.FAILED
    job.lease_until = None
    job.next_attempt_at = None
    job.error_code = error_code[:60]
    job.last_error_at = now
    await db.flush()


async def create_pending_relationship_analysis(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    relationship_type: str,
    calculation_a_id: uuid.UUID,
    calculation_b_id: uuid.UUID,
    calculation_version: str,
    knowledge_version: str,
    prompt_version: str,
) -> RelationshipAnalysis:
    analysis = RelationshipAnalysis(
        workspace_id=workspace_id,
        job_id=job_id,
        relationship_type=relationship_type,
        calculation_a_id=calculation_a_id,
        calculation_b_id=calculation_b_id,
        calculation_version=calculation_version,
        knowledge_version=knowledge_version,
        prompt_version=prompt_version,
        status="PENDING",
    )
    db.add(analysis)
    await db.flush()
    return analysis


async def create_pending_shadow_dynamics_analysis(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    job_id: uuid.UUID,
    relationship_type: str,
    calculation_a_id: uuid.UUID,
    calculation_b_id: uuid.UUID,
    calculation_version: str,
    knowledge_version: str,
    prompt_version: str,
) -> ShadowDynamicsAnalysis:
    analysis = ShadowDynamicsAnalysis(
        workspace_id=workspace_id,
        job_id=job_id,
        relationship_type=relationship_type,
        calculation_a_id=calculation_a_id,
        calculation_b_id=calculation_b_id,
        calculation_version=calculation_version,
        knowledge_version=knowledge_version,
        prompt_version=prompt_version,
        status="PENDING",
    )
    db.add(analysis)
    await db.flush()
    return analysis


async def get_relationship_analysis_for_job(
    db: AsyncSession, *, job_id: uuid.UUID
) -> RelationshipAnalysis | None:
    stmt = select(RelationshipAnalysis).where(RelationshipAnalysis.job_id == job_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_shadow_dynamics_analysis_for_job(
    db: AsyncSession, *, job_id: uuid.UUID
) -> ShadowDynamicsAnalysis | None:
    stmt = select(ShadowDynamicsAnalysis).where(ShadowDynamicsAnalysis.job_id == job_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def finalize_relationship_analysis(
    db: AsyncSession,
    *,
    analysis: RelationshipAnalysis,
    result_json: dict[str, Any],
    model_provider: str,
    model_name: str,
    generated_at: dt.datetime,
) -> None:
    analysis.status = "COMPLETE"
    analysis.result_json = result_json
    analysis.model_provider = model_provider
    analysis.model_name = model_name
    analysis.generated_at = generated_at
    await db.flush()


async def finalize_shadow_dynamics_analysis(
    db: AsyncSession,
    *,
    analysis: ShadowDynamicsAnalysis,
    result_json: dict[str, Any],
    model_provider: str,
    model_name: str,
    generated_at: dt.datetime,
) -> None:
    analysis.status = "COMPLETE"
    analysis.result_json = result_json
    analysis.model_provider = model_provider
    analysis.model_name = model_name
    analysis.generated_at = generated_at
    await db.flush()


async def fail_relationship_analysis(db: AsyncSession, *, analysis: RelationshipAnalysis) -> None:
    analysis.status = "FAILED"
    await db.flush()


async def fail_shadow_dynamics_analysis(
    db: AsyncSession, *, analysis: ShadowDynamicsAnalysis
) -> None:
    analysis.status = "FAILED"
    await db.flush()


async def get_latest_relationship_analysis_for_workspace(
    db: AsyncSession, *, workspace_id: uuid.UUID
) -> RelationshipAnalysis | None:
    stmt = (
        select(RelationshipAnalysis)
        .where(
            RelationshipAnalysis.workspace_id == workspace_id,
            RelationshipAnalysis.status == "COMPLETE",
        )
        .order_by(RelationshipAnalysis.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_latest_shadow_dynamics_for_workspace(
    db: AsyncSession, *, workspace_id: uuid.UUID
) -> ShadowDynamicsAnalysis | None:
    stmt = (
        select(ShadowDynamicsAnalysis)
        .where(
            ShadowDynamicsAnalysis.workspace_id == workspace_id,
            ShadowDynamicsAnalysis.status == "COMPLETE",
        )
        .order_by(ShadowDynamicsAnalysis.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_relationship_analysis_for_user(
    db: AsyncSession, *, analysis_id: uuid.UUID, user_id: uuid.UUID
) -> RelationshipAnalysis | None:
    """IDOR gate: readable by any ACTIVE workspace member -- same rationale as
    `get_analysis_job_for_user`. A previously COMPLETE analysis stays readable even
    after a later consent revoke (specs/v2/shadow-dynamics-spec.md "Regenerierung nach
    Revoke": historical snapshot) -- consent is checked only at job-creation time
    (`services/relationship_analysis_service.py`), never here."""
    stmt = (
        select(RelationshipAnalysis)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == RelationshipAnalysis.workspace_id)
        .where(
            RelationshipAnalysis.id == analysis_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_shadow_dynamics_analysis_for_user(
    db: AsyncSession, *, analysis_id: uuid.UUID, user_id: uuid.UUID
) -> ShadowDynamicsAnalysis | None:
    stmt = (
        select(ShadowDynamicsAnalysis)
        .join(WorkspaceMember, WorkspaceMember.workspace_id == ShadowDynamicsAnalysis.workspace_id)
        .where(
            ShadowDynamicsAnalysis.id == analysis_id,
            WorkspaceMember.user_id == user_id,
            WorkspaceMember.status == WorkspaceMemberStatus.ACTIVE,
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
