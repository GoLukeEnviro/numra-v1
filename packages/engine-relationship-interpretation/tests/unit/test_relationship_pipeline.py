from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from numra_interpretation.knowledge_loader import load_knowledge_base
from numra_interpretation.llm.mock_provider import MockLLMProvider
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput
from numra_relationship_interpretation.knowledge_loader import (
    load_relationship_frame,
    load_shadow_interaction_rules,
)
from numra_relationship_interpretation.pipeline import (
    generate_relationship_analysis,
    generate_shadow_dynamics,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[4]
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"

_COMPATIBILITY_PATTERN = re.compile(r"\d+\s*%.*(kompatib|match|übereinstimm)", re.IGNORECASE)


@pytest.fixture(scope="module")
def knowledge_base():
    return load_knowledge_base(KNOWLEDGE_ROOT)


@pytest.fixture(scope="module")
def profile_a():
    person = PersonInput(
        birth_first_names="Anna",
        birth_middle_names="Marie",
        birth_last_name="Berger",
        birth_date=dt.date(1990, 3, 14),
    )
    return calculate_profile(person, as_of_date=dt.date(2026, 8, 19))


@pytest.fixture(scope="module")
def profile_b():
    person = PersonInput(
        birth_first_names="Ben",
        birth_middle_names=None,
        birth_last_name="Fischer",
        birth_date=dt.date(1988, 7, 22),
    )
    return calculate_profile(person, as_of_date=dt.date(2026, 8, 19))


@pytest.mark.asyncio
async def test_generate_relationship_analysis_covers_all_partner_dimensions(
    profile_a, profile_b
) -> None:
    frame = load_relationship_frame(KNOWLEDGE_ROOT, "PARTNER")
    assert frame is not None
    result = await generate_relationship_analysis(
        profile_a=profile_a,
        profile_b=profile_b,
        relationship_type="PARTNER",
        frame_knowledge=frame,
        llm=MockLLMProvider(),
        knowledge_version="0.1.0",
    )
    assert result.relationship_type == "PARTNER"
    dimension_ids = {d.dimension_id for d in result.dimensions}
    assert dimension_ids == {
        "communication",
        "closeness",
        "autonomy",
        "needs",
        "strengths",
        "conflict_dynamics",
    }
    for dimension in result.dimensions:
        assert len(dimension.statements) >= 1
        for statement in dimension.statements:
            assert statement.canonical_refs or statement.knowledge_refs
            assert not _COMPATIBILITY_PATTERN.search(statement.text)


@pytest.mark.asyncio
async def test_generate_shadow_dynamics_full_provenance(
    profile_a, profile_b, knowledge_base
) -> None:
    rules = load_shadow_interaction_rules(KNOWLEDGE_ROOT)
    result = await generate_shadow_dynamics(
        profile_a=profile_a,
        profile_b=profile_b,
        relationship_type="PARTNER",
        knowledge=knowledge_base,
        shadow_rules=rules,
        llm=MockLLMProvider(),
        knowledge_version="0.1.0",
    )
    all_statements = (
        list(result.user_a_shadow_themes)
        + list(result.user_b_shadow_themes)
        + [result.interaction_pattern, result.escalation_loop]
        + list(result.deescalation_opportunities)
    )
    for statement in all_statements:
        assert statement.canonical_refs or statement.knowledge_refs
        assert not _COMPATIBILITY_PATTERN.search(statement.text)
    assert result.pattern_intensity in ("moderate", "high")
    assert len(result.recommended_micro_tasks) >= 1


@pytest.mark.asyncio
async def test_generate_relationship_analysis_mismatched_type_raises(profile_a, profile_b) -> None:
    frame = load_relationship_frame(KNOWLEDGE_ROOT, "PARTNER")
    assert frame is not None
    with pytest.raises(ValueError):
        await generate_relationship_analysis(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type="FRIENDSHIP",
            frame_knowledge=frame,
            llm=MockLLMProvider(),
            knowledge_version="0.1.0",
        )
