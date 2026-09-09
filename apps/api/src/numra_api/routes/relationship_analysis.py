from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, rate_limit_by_user, require_csrf
from numra_api.models import AnalysisJob, RelationshipAnalysis, ShadowDynamicsAnalysis, User
from numra_api.repositories.analysis import (
    get_analysis_job_for_user,
    get_latest_relationship_analysis_for_workspace,
    get_latest_shadow_dynamics_for_workspace,
    get_relationship_analysis_for_user,
    get_shadow_dynamics_analysis_for_user,
)
from numra_api.repositories.workspaces import get_workspace_member
from numra_api.schemas.relationship_analysis import (
    AnalysisJobOut,
    RelationshipAnalysisOut,
    ShadowDynamicsAnalysisOut,
)
from numra_api.services.errors import NotFoundError
from numra_api.services.feature_flags import require_v2_phase
from numra_api.services.relationship_analysis_service import (
    create_relationship_analysis_job,
    create_shadow_dynamics_job,
)


async def _require_membership(
    db: AsyncSession, *, workspace_id: uuid.UUID, user_id: uuid.UUID
) -> None:
    """IDOR gate for the two "latest" GET routes -- `get_latest_*_for_workspace`
    repository calls themselves are not user-scoped (they only need `workspace_id`),
    so membership is checked here before calling them."""
    member = await get_workspace_member(db, workspace_id=workspace_id, user_id=user_id)
    if member is None:
        raise NotFoundError(f"workspace {workspace_id} not found")


router = APIRouter(
    prefix="/v1",
    tags=["relationship-analysis"],
    dependencies=[Depends(require_v2_phase("relationship_workspaces"))],
)


def _job_to_out(job: AnalysisJob) -> AnalysisJobOut:
    return AnalysisJobOut(
        id=job.id,
        workspace_id=job.workspace_id,
        analysis_type=job.analysis_type,
        status=job.status,
        progress=job.progress,
        attempt_count=job.attempt_count,
        error_code=job.error_code,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _relationship_analysis_to_out(analysis: RelationshipAnalysis) -> RelationshipAnalysisOut:
    return RelationshipAnalysisOut(
        id=analysis.id,
        workspace_id=analysis.workspace_id,
        job_id=analysis.job_id,
        relationship_type=analysis.relationship_type,
        calculation_version=analysis.calculation_version,
        knowledge_version=analysis.knowledge_version,
        prompt_version=analysis.prompt_version,
        model_provider=analysis.model_provider,
        model_name=analysis.model_name,
        status=analysis.status,
        result=analysis.result_json,
        generated_at=analysis.generated_at,
        created_at=analysis.created_at,
    )


def _shadow_dynamics_to_out(analysis: ShadowDynamicsAnalysis) -> ShadowDynamicsAnalysisOut:
    return ShadowDynamicsAnalysisOut(
        id=analysis.id,
        workspace_id=analysis.workspace_id,
        job_id=analysis.job_id,
        relationship_type=analysis.relationship_type,
        calculation_version=analysis.calculation_version,
        knowledge_version=analysis.knowledge_version,
        prompt_version=analysis.prompt_version,
        model_provider=analysis.model_provider,
        model_name=analysis.model_name,
        status=analysis.status,
        result=analysis.result_json,
        generated_at=analysis.generated_at,
        created_at=analysis.created_at,
    )


@router.post(
    "/workspaces/{workspace_id}/relationship-analysis",
    response_model=RelationshipAnalysisOut,
    status_code=201,
    dependencies=[
        Depends(require_csrf),
        Depends(rate_limit_by_user("relationship-analysis:create", limit=30, window_seconds=3600)),
    ],
)
async def create_relationship_analysis_route(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> RelationshipAnalysisOut:
    _job, analysis = await create_relationship_analysis_job(
        db, workspace_id=workspace_id, requester_user_id=user.id, idempotency_key=idempotency_key
    )
    return _relationship_analysis_to_out(analysis)


@router.get(
    "/workspaces/{workspace_id}/relationship-analysis",
    response_model=RelationshipAnalysisOut,
)
async def get_latest_relationship_analysis_route(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RelationshipAnalysisOut:
    await _require_membership(db, workspace_id=workspace_id, user_id=user.id)
    analysis = await get_latest_relationship_analysis_for_workspace(db, workspace_id=workspace_id)
    if analysis is None:
        raise NotFoundError(f"no relationship analysis for workspace {workspace_id}")
    return _relationship_analysis_to_out(analysis)


@router.get(
    "/workspaces/{workspace_id}/relationship-analysis/{analysis_id}",
    response_model=RelationshipAnalysisOut,
)
async def get_relationship_analysis_route(
    workspace_id: uuid.UUID,  # noqa: ARG001 - path is namespaced under the workspace for URL clarity
    analysis_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RelationshipAnalysisOut:
    analysis = await get_relationship_analysis_for_user(
        db, analysis_id=analysis_id, user_id=user.id
    )
    if analysis is None:
        raise NotFoundError(f"relationship analysis {analysis_id} not found")
    return _relationship_analysis_to_out(analysis)


@router.post(
    "/workspaces/{workspace_id}/shadow-dynamics",
    response_model=ShadowDynamicsAnalysisOut,
    status_code=201,
    dependencies=[
        Depends(require_csrf),
        Depends(rate_limit_by_user("shadow-dynamics:create", limit=30, window_seconds=3600)),
    ],
)
async def create_shadow_dynamics_route(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ShadowDynamicsAnalysisOut:
    _job, analysis = await create_shadow_dynamics_job(
        db, workspace_id=workspace_id, requester_user_id=user.id, idempotency_key=idempotency_key
    )
    return _shadow_dynamics_to_out(analysis)


@router.get(
    "/workspaces/{workspace_id}/shadow-dynamics",
    response_model=ShadowDynamicsAnalysisOut,
)
async def get_latest_shadow_dynamics_route(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShadowDynamicsAnalysisOut:
    await _require_membership(db, workspace_id=workspace_id, user_id=user.id)
    analysis = await get_latest_shadow_dynamics_for_workspace(db, workspace_id=workspace_id)
    if analysis is None:
        raise NotFoundError(f"no shadow dynamics analysis for workspace {workspace_id}")
    return _shadow_dynamics_to_out(analysis)


@router.get(
    "/workspaces/{workspace_id}/shadow-dynamics/{analysis_id}",
    response_model=ShadowDynamicsAnalysisOut,
)
async def get_shadow_dynamics_route(
    workspace_id: uuid.UUID,  # noqa: ARG001 - path is namespaced under the workspace for URL clarity
    analysis_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShadowDynamicsAnalysisOut:
    analysis = await get_shadow_dynamics_analysis_for_user(
        db, analysis_id=analysis_id, user_id=user.id
    )
    if analysis is None:
        raise NotFoundError(f"shadow dynamics analysis {analysis_id} not found")
    return _shadow_dynamics_to_out(analysis)


@router.get("/analysis-jobs/{job_id}", response_model=AnalysisJobOut)
async def get_analysis_job_route(
    job_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalysisJobOut:
    job = await get_analysis_job_for_user(db, job_id=job_id, user_id=user.id)
    if job is None:
        raise NotFoundError(f"analysis job {job_id} not found")
    return _job_to_out(job)
