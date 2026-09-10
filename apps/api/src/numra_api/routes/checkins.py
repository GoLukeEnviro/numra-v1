"""specs/v2/checkin-spec.md -- configurable Relationship Check-ins
(PR-V2-06). No admin endpoint exists here for check-in data (spec: "niemals, unter
keiner Rolle") and every route below gates on `get_workspace_member` first,
returning 404 (never 403) for a non-member -- same IDOR pattern as
routes/relationship_workspaces.py / routes/consent.py.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header, Query
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
    CheckinErrorOut,
    CheckinOut,
    CheckinResponseOut,
    CheckinRoundDimensionOut,
    CheckinRoundOut,
    CheckinRoundStartRequest,
    CheckinSubmitRequest,
    CheckinSummaryOut,
    CheckinTemplateOut,
)
from numra_api.services.checkin_service import (
    CheckinSubmissionResult,
    create_custom_dimension,
    get_checkin,
    get_checkin_template,
    get_current_checkin,
    list_checkins,
    start_checkin_round,
    submit_checkin,
    update_dimension,
)
from numra_api.services.feature_flags import require_v2_phase

router = APIRouter(
    prefix="/v1/workspaces/{workspace_id}",
    tags=["checkins"],
    responses={
        404: {
            "model": CheckinErrorOut,
            "description": "Workspace/resource not available to caller",
        },
        409: {
            "model": CheckinErrorOut,
            "description": (
                "WORKSPACE_DISSOLVED, CHECKIN_ROUND_OPEN, CHECKIN_ROUND_MISMATCH, "
                "CHECKIN_ALREADY_SUBMITTED, CHECKIN_IDEMPOTENCY_CONFLICT or SEMANTIC_KEY_IMMUTABLE"
            ),
        },
        422: {
            "model": CheckinErrorOut,
            "description": (
                "CHECKIN_REQUEST_INVALID, CHECKIN_RESPONSES_INCOMPLETE, "
                "CHECKIN_VALUE_OUT_OF_RANGE, "
                "CHECKIN_SCALE_INVALID, CHECKIN_NO_ACTIVE_DIMENSIONS or "
                "DIMENSION_NOT_ALLOWED_FOR_RELATIONSHIP_TYPE; no submitted values are echoed"
            ),
        },
    },
    dependencies=[Depends(require_v2_phase("checkins"))],
)


def _dimension_to_out(dimension: CheckinDimension) -> CheckinDimensionOut:
    return CheckinDimensionOut.model_validate(dimension, from_attributes=True)


def _response_to_out(response: CheckinResponse) -> CheckinResponseOut:
    return CheckinResponseOut.model_validate(response, from_attributes=True)


def _analysis_to_out(analysis: CheckinAnalysis | None) -> CheckinAnalysisOut | None:
    if analysis is None:
        return None
    return CheckinAnalysisOut(computed_at=analysis.computed_at, result=analysis.result_json)


def _checkin_to_out(result: CheckinSubmissionResult) -> CheckinOut:
    checkin = result.checkin
    return CheckinOut(
        id=checkin.id,
        workspace_id=checkin.workspace_id,
        checkin_template_version=checkin.checkin_template_version,
        status=checkin.status,
        cycle_started_at=checkin.cycle_started_at,
        snapshot_origin=checkin.snapshot_origin,
        snapshot_recorded=checkin.snapshot_origin != "LEGACY_MISSING",
        dimensions=[CheckinRoundDimensionOut.model_validate(d) for d in result.dimensions],
        my_responses=[_response_to_out(r) for r in result.my_responses],
        partner_submitted=result.partner_submitted,
        analysis=_analysis_to_out(result.analysis),
    )


def _checkin_to_summary(checkin: RelationshipCheckin) -> CheckinSummaryOut:
    return CheckinSummaryOut.model_validate(checkin, from_attributes=True)


@router.get("/checkin-template", response_model=CheckinTemplateOut)
async def get_checkin_template_route(
    workspace_id: uuid.UUID,
    version: int | None = Query(default=None, ge=1),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> CheckinTemplateOut:
    template, dimensions = await get_checkin_template(
        db, workspace_id=workspace_id, user_id=user.id, version=version
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
    db: AsyncSession = Depends(get_db, scope="function"),
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
        dimension_class=body.dimension_class,
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
    db: AsyncSession = Depends(get_db, scope="function"),
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
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> CheckinOut:
    result = await submit_checkin(
        db,
        workspace_id=workspace_id,
        user_id=user.id,
        responses=[(r.dimension_id, r.value) for r in body.responses],
        round_id=body.round_id,
        idempotency_key=idempotency_key,
    )
    return _checkin_to_out(result)


@router.post(
    "/checkins/rounds",
    response_model=CheckinRoundOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def start_checkin_round_route(
    workspace_id: uuid.UUID,
    body: CheckinRoundStartRequest | None = None,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> CheckinRoundOut:
    """Start explicitly; replay returns this round's current authorized state."""
    result = await start_checkin_round(
        db, workspace_id=workspace_id, user_id=user.id, idempotency_key=idempotency_key
    )
    return _checkin_to_out(result)


@router.get("/checkins/current", response_model=CheckinOut | None)
async def get_current_checkin_route(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> CheckinOut | None:
    """Open round, else latest completed round; JSON null when none exists."""
    result = await get_current_checkin(db, workspace_id=workspace_id, user_id=user.id)
    return _checkin_to_out(result) if result is not None else None


@router.get("/checkins/{checkin_id}", response_model=CheckinOut)
async def get_checkin_route(
    workspace_id: uuid.UUID,
    checkin_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> CheckinOut:
    result = await get_checkin(
        db, workspace_id=workspace_id, user_id=user.id, checkin_id=checkin_id
    )
    return _checkin_to_out(result)


@router.get("/checkins", response_model=list[CheckinSummaryOut])
async def list_checkins_route(
    workspace_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db, scope="function"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CheckinSummaryOut]:
    checkins = await list_checkins(
        db, workspace_id=workspace_id, user_id=user.id, limit=limit, offset=offset
    )
    return [_checkin_to_summary(c) for c in checkins]
