from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, require_csrf
from numra_api.models import RelationshipComparison, User
from numra_api.repositories.calculations import get_calculation_for_user
from numra_api.schemas.relationship import RelationshipCreateRequest, RelationshipOut
from numra_api.services.errors import NotFoundError
from numra_api.services.relationship_service import build_relationship_comparison

router = APIRouter(prefix="/v1/relationships", tags=["relationships"])


def _to_out(rel: RelationshipComparison) -> RelationshipOut:
    return RelationshipOut(
        id=str(rel.id),
        calculation_a_id=str(rel.calculation_a_id),
        calculation_b_id=str(rel.calculation_b_id),
        comparison=rel.comparison_json,
        created_at=rel.created_at,
    )


@router.post(
    "", response_model=RelationshipOut, status_code=201, dependencies=[Depends(require_csrf)]
)
async def create_relationship_route(
    body: RelationshipCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RelationshipOut:
    calc_a = await get_calculation_for_user(
        db, calculation_id=uuid.UUID(body.calculation_a_id), user_id=user.id
    )
    calc_b = await get_calculation_for_user(
        db, calculation_id=uuid.UUID(body.calculation_b_id), user_id=user.id
    )
    if calc_a is None or calc_b is None:
        raise NotFoundError("one or both calculations not found")

    comparison = build_relationship_comparison(
        calc_a.canonical_profile_json, calc_b.canonical_profile_json
    )
    relationship = RelationshipComparison(
        user_id=user.id,
        calculation_a_id=calc_a.id,
        calculation_b_id=calc_b.id,
        comparison_json=comparison,
    )
    db.add(relationship)
    await db.flush()
    return _to_out(relationship)


@router.get("/{relationship_id}", response_model=RelationshipOut)
async def get_relationship_route(
    relationship_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RelationshipOut:
    relationship = await db.get(RelationshipComparison, relationship_id)
    if relationship is None or relationship.user_id != user.id:
        raise NotFoundError(f"relationship {relationship_id} not found")
    return _to_out(relationship)
