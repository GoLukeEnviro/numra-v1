from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.deps import get_current_user, get_db, require_csrf
from numra_api.models import Person, RelationshipComparison, User
from numra_api.repositories.calculations import (
    get_calculation_for_user,
    get_latest_calculation_for_person,
)
from numra_api.repositories.relationships import (
    get_relationship_with_people_for_user,
    list_relationships_for_user,
)
from numra_api.schemas.person_ref import PersonRefOut, person_display_name
from numra_api.schemas.relationship import (
    RelationshipCreateRequest,
    RelationshipInsightOut,
    RelationshipOut,
    RelationshipSummaryOut,
)
from numra_api.services.errors import NotFoundError
from numra_api.services.relationship_service import (
    build_relationship_comparison,
    build_relationship_insights,
)

router = APIRouter(prefix="/v1/relationships", tags=["relationships"])


def _person_ref(person: Person) -> PersonRefOut:
    return PersonRefOut(
        id=person.id,
        display_name=person_display_name(
            preferred_name=person.preferred_name,
            birth_first_names=person.birth_first_names,
            birth_last_name=person.birth_last_name,
        ),
    )


def _to_out(rel: RelationshipComparison, person_a: Person, person_b: Person) -> RelationshipOut:
    return RelationshipOut(
        id=str(rel.id),
        calculation_a_id=str(rel.calculation_a_id),
        calculation_b_id=str(rel.calculation_b_id),
        person_a=_person_ref(person_a),
        person_b=_person_ref(person_b),
        comparison=rel.comparison_json,
        insights=tuple(
            RelationshipInsightOut.model_validate(insight) for insight in rel.insights_json
        ),
        created_at=rel.created_at,
    )


def _to_summary(
    rel: RelationshipComparison, person_a: Person, person_b: Person
) -> RelationshipSummaryOut:
    return RelationshipSummaryOut(
        id=str(rel.id),
        person_a=_person_ref(person_a),
        person_b=_person_ref(person_b),
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
    if body.person_a_id is not None and body.person_b_id is not None:
        # V1.5 Epic E: the product-facing path -- resolve each person's latest
        # calculation server-side rather than making the user paste a calculation
        # UUID. A person with no calculation yet gets a specific, actionable error
        # (not a generic "not found") so the frontend can offer "Run calculation".
        person_a_id = uuid.UUID(body.person_a_id)
        person_b_id = uuid.UUID(body.person_b_id)
        calc_a = await get_latest_calculation_for_person(db, person_id=person_a_id, user_id=user.id)
        if calc_a is None:
            raise NotFoundError(f"person {person_a_id} has no calculation yet")
        calc_b = await get_latest_calculation_for_person(db, person_id=person_b_id, user_id=user.id)
        if calc_b is None:
            raise NotFoundError(f"person {person_b_id} has no calculation yet")
    else:
        assert body.calculation_a_id is not None
        assert body.calculation_b_id is not None
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
    insights = build_relationship_insights(
        calc_a.canonical_profile_json, calc_b.canonical_profile_json
    )
    relationship = RelationshipComparison(
        user_id=user.id,
        calculation_a_id=calc_a.id,
        calculation_b_id=calc_b.id,
        comparison_json=comparison,
        insights_json=insights,
    )
    db.add(relationship)
    await db.flush()

    row = await get_relationship_with_people_for_user(
        db, relationship_id=relationship.id, user_id=user.id
    )
    assert row is not None
    return _to_out(*row)


@router.get("", response_model=list[RelationshipSummaryOut])
async def list_relationships_route(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[RelationshipSummaryOut]:
    rows = await list_relationships_for_user(db, user_id=user.id, limit=limit, offset=offset)
    return [_to_summary(rel, person_a, person_b) for rel, person_a, person_b in rows]


@router.get("/{relationship_id}", response_model=RelationshipOut)
async def get_relationship_route(
    relationship_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RelationshipOut:
    row = await get_relationship_with_people_for_user(
        db, relationship_id=relationship_id, user_id=user.id
    )
    if row is None:
        raise NotFoundError(f"relationship {relationship_id} not found")
    return _to_out(*row)
