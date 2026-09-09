"""PR-V2-11 -- Evidence Results (reine Lese-Berechnung) und Pattern Analyses
(explizit gespeicherte Snapshots), specs/v2/evidence-policy.md.

`GET .../evidence-results` persistiert nichts. `POST .../pattern-analyses` nimmt
dieselben Parameter entgegen, rechnet ueber DENSELBEN Servicepfad neu und speichert
erst das Ergebnis dieser Neuberechnung -- ein clientgelieferter Result-Payload wird
nirgends akzeptiert.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, require_csrf
from numra_api.models import PatternAnalysis, User
from numra_api.models.enums import CorrelationTarget
from numra_api.repositories.evidence import (
    delete_pattern_analysis,
    get_pattern_analysis_for_user,
    list_pattern_analyses_for_person,
)
from numra_api.repositories.people import get_person
from numra_api.schemas.evidence import (
    EvidenceResultOut,
    PatternAnalysisCreateRequest,
    PatternAnalysisOut,
)
from numra_api.services.errors import NotFoundError
from numra_api.services.evidence_service import (
    compute_evidence_result_for_person,
    save_pattern_analysis,
)
from numra_api.services.feature_flags import require_v2_phase

router = APIRouter(
    prefix="/v1",
    tags=["evidence"],
    dependencies=[Depends(require_v2_phase("evidence_layer"))],
)


def _to_analysis_out(analysis: PatternAnalysis) -> PatternAnalysisOut:
    return PatternAnalysisOut(
        id=analysis.id,
        person_id=analysis.person_id,
        evidence_policy_version=analysis.evidence_policy_version,
        metric_key=analysis.metric_key,
        correlation_target=CorrelationTarget(analysis.correlation_target),
        correlation_target_value=analysis.correlation_target_value,
        result=EvidenceResultOut.model_validate(analysis.result_json),
        created_at=analysis.created_at,
    )


@router.get("/people/{person_id}/evidence-results", response_model=EvidenceResultOut)
async def get_evidence_result_route(
    person_id: uuid.UUID,
    metric_key: str = Query(min_length=1, max_length=60),
    correlation_target: CorrelationTarget = Query(),
    correlation_target_value: int = Query(ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvidenceResultOut:
    """Antwortet immer mit 200, sobald Person und Metrik existieren --
    `confidence_category=NO_RELIABLE_PATTERN` ist ein Ergebnis, kein Fehler."""
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")

    result = await compute_evidence_result_for_person(
        db,
        person=person,
        metric_key=metric_key,
        correlation_target=correlation_target,
        correlation_target_value=correlation_target_value,
    )
    return EvidenceResultOut.model_validate(result)


@router.post(
    "/people/{person_id}/pattern-analyses",
    response_model=PatternAnalysisOut,
    status_code=201,
    dependencies=[Depends(require_csrf)],
)
async def create_pattern_analysis_route(
    person_id: uuid.UUID,
    body: PatternAnalysisCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PatternAnalysisOut:
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")

    analysis = await save_pattern_analysis(
        db,
        person=person,
        user_id=user.id,
        metric_key=body.metric_key,
        correlation_target=body.correlation_target,
        correlation_target_value=body.correlation_target_value,
    )
    return _to_analysis_out(analysis)


@router.get("/people/{person_id}/pattern-analyses", response_model=list[PatternAnalysisOut])
async def list_pattern_analyses_route(
    person_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[PatternAnalysisOut]:
    person = await get_person(db, person_id=person_id, user_id=user.id)
    if person is None:
        raise NotFoundError(f"person {person_id} not found")

    analyses = await list_pattern_analyses_for_person(
        db, person_id=person_id, user_id=user.id, limit=limit, offset=offset
    )
    return [_to_analysis_out(analysis) for analysis in analyses]


@router.get("/pattern-analyses/{analysis_id}", response_model=PatternAnalysisOut)
async def get_pattern_analysis_route(
    analysis_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PatternAnalysisOut:
    analysis = await get_pattern_analysis_for_user(db, analysis_id=analysis_id, user_id=user.id)
    if analysis is None:
        raise NotFoundError(f"pattern analysis {analysis_id} not found")
    return _to_analysis_out(analysis)


@router.delete(
    "/pattern-analyses/{analysis_id}", status_code=204, dependencies=[Depends(require_csrf)]
)
async def delete_pattern_analysis_route(
    analysis_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    analysis = await get_pattern_analysis_for_user(db, analysis_id=analysis_id, user_id=user.id)
    if analysis is None:
        raise NotFoundError(f"pattern analysis {analysis_id} not found")
    await delete_pattern_analysis(db, analysis=analysis)
