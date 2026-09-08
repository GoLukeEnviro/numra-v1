"""specs/v2/checkin-spec.md -- configurable Relationship Check-ins
(PR-V2-06). No admin endpoint exists here for check-in data (spec: "niemals, unter
keiner Rolle") and every route below gates on `get_workspace_member` first,
returning 404 (never 403) for a non-member -- same IDOR pattern as
routes/relationship_workspaces.py / routes/consent.py.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, require_csrf
from numra_api.models import (
    CheckinAnalysis,
    CheckinDimension,
    CheckinResponse,
    RelationshipCheckin,
    User,
)
from numra_api.schemas.checkin import (
    CheckinAnalysisOut,
    CheckinDimensionCreateRequest,
    CheckinDimensionOut,
    CheckinDimensionUpdateRequest,
    CheckinOut,
    CheckinResponseOut,
    CheckinSubmitRequest,
    CheckinSummaryOut,
    CheckinTemplateOut,
)
from numra_api.services.checkin_service import (
    create_custom_dimension,
    get_checkin,
    get_checkin_template,
    list_checkins,
    submit_checkin,
    update_dimension,
)

router = APIRouter(prefix="/v1/workspaces/{workspace_id}", tags=["checkins"])


def _dimension_to_out(dimension: CheckinDimension) -> CheckinDimensionOut:
    return CheckinDimensionOut.model_validate(dimension, from_attributes=True)


def _response_to_out(response: CheckinResponse) -> CheckinResponseOut:
    return CheckinResponseOut.model_validate(response, from_attributes=True)


def _analysis_to_out(analysis: CheckinAnalysis | None) -> CheckinAnalysisOut | None:
    if analysis is None:
        return None
    return CheckinAnalysisOut(computed_at=analysis.computed_at, result=analysis.result_json)


def _checkin_to_out(
    checkin: RelationshipCheckin,
    my_responses: list[CheckinResponse],
    analysis: CheckinAnalysis | None,
) -> CheckinOut:
    return CheckinOut(
        id=checkin.id,
        workspace_id=checkin.workspace_id,
        checkin_template_version=checkin.checkin_template_version,
        status=checkin.status,
        cycle_started_at=checkin.cycle_started_at,
        my_responses=[_response_to_out(r) for r in my_responses],
        analysis=_analysis_to_out(analysis),
    )


def _checkin_to_summary(checkin: RelationshipCheckin) -> CheckinSummaryOut:
    return CheckinSummaryOut.model_validate(checkin, from_attributes=True)


@router.get("/checkin-template", response_model=CheckinTemplateOut)
async def get_checkin_template_route(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckinTemplateOut:
    template, dimensions = await get_checkin_template(
        db, workspace_id=workspace_id, user_id=user.id
    )
    return CheckinTemplateOut(
        id=template.id,
        version=template.version,
        active=template.active,
        dimensions=[_dimension_to_out(d) for d in dimensions],
    )


@router.post(
    "/checkin-dimensions",
    response_model=CheckinDimensionOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def create_checkin_dimension_route(
    workspace_id: uuid.UUID,
    body: CheckinDimensionCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckinDimensionOut:
    dimension = await create_custom_dimension(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        semantic_key=body.semantic_key,
        label=body.label,
        description=body.description,
        scale_min=body.scale_min,
        scale_max=body.scale_max,
        sort_order=body.sort_order,
    )
    return _dimension_to_out(dimension)


@router.patch(
    "/checkin-dimensions/{dimension_id}",
    response_model=CheckinDimensionOut,
    dependencies=[Depends(require_csrf)],
)
async def update_checkin_dimension_route(
    workspace_id: uuid.UUID,
    dimension_id: uuid.UUID,
    body: CheckinDimensionUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckinDimensionOut:
    dimension = await update_dimension(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        dimension_id=dimension_id,
        label=body.label,
        description=body.description,
        active=body.active,
    )
    return _dimension_to_out(dimension)


@router.post(
    "/checkins", response_model=CheckinOut, status_code=201, dependencies=[Depends(require_csrf)]
)
async def submit_checkin_route(
    workspace_id: uuid.UUID,
    body: CheckinSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckinOut:
    result = await submit_checkin(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        responses=[(r.dimension_id, r.value) for r in body.responses],
    )
    return _checkin_to_out(result.checkin, result.my_responses, result.analysis)


@router.get("/checkins/{checkin_id}", response_model=CheckinOut)
async def get_checkin_route(
    workspace_id: uuid.UUID,
    checkin_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckinOut:
    checkin, my_responses, analysis = await get_checkin(
        db, workspace_id=workspace_id, user_id=user.id, checkin_id=checkin_id
    )
    return _checkin_to_out(checkin, my_responses, analysis)


@router.get("/checkins", response_model=list[CheckinSummaryOut])
async def list_checkins_route(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CheckinSummaryOut]:
    checkins = await list_checkins(
        db, workspace_id=workspace_id, user_id=user.id, limit=limit, offset=offset
    )
    return [_checkin_to_summary(c) for c in checkins]
