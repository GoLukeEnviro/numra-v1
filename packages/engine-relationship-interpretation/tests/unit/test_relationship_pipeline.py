from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from numra_interpretation.knowledge_loader import load_knowledge_base
from numra_interpretation.llm.mock_provider import MockLLMProvider
from numra_interpretation.llm.types import (
    GenerationRequest,
    GenerationResult,
    ProviderHealth,
    StructuredGenerationRequest,
)
from numra_interpretation.llm.validator import build_metric_display_value_index
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput
from numra_relationship_interpretation.errors import AnalysisGenerationError
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
async def test_generate_shadow_dynamics_ab_direction_is_symmetric(
    profile_a, profile_b, knowledge_base
) -> None:
    """Swapping the (a, b) argument order must swap `user_a`/`user_b` shadow themes and
    their `metric:a:` / `metric:b:` canonical refs consistently -- no fact stays pinned
    to the wrong person."""
    rules = load_shadow_interaction_rules(KNOWLEDGE_ROOT)

    async def _run(pa, pb):
        return await generate_shadow_dynamics(
            profile_a=pa,
            profile_b=pb,
            relationship_type="PARTNER",
            knowledge=knowledge_base,
            shadow_rules=rules,
            llm=MockLLMProvider(),
            knowledge_version="0.2.0",
        )

    forward = await _run(profile_a, profile_b)
    swapped = await _run(profile_b, profile_a)

    fwd_a = forward.user_a_shadow_themes[0].knowledge_refs
    fwd_b = forward.user_b_shadow_themes[0].knowledge_refs
    swp_a = swapped.user_a_shadow_themes[0].knowledge_refs
    swp_b = swapped.user_b_shadow_themes[0].knowledge_refs

    assert fwd_a == swp_b
    assert fwd_b == swp_a
    assert fwd_a != fwd_b
    assert forward.user_a_shadow_themes[0].canonical_refs == ("metric:a:life_path",)
    assert swapped.user_a_shadow_themes[0].canonical_refs == ("metric:a:life_path",)


@pytest.mark.asyncio
async def test_generate_shadow_dynamics_missing_rule_raises_generation_error(
    profile_a, profile_b, knowledge_base
) -> None:
    """A shadow-theme pair with no rules.yaml row surfaces as `AnalysisGenerationError`
    (via the `ShadowInteractionRuleMissing` subclass), never a bare exception -- checked
    here with a deliberately empty rules table, not a real knowledge gap."""
    with pytest.raises(AnalysisGenerationError):
        await generate_shadow_dynamics(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type="PARTNER",
            knowledge=knowledge_base,
            shadow_rules=(),
            llm=MockLLMProvider(),
            knowledge_version="0.2.0",
        )


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


@pytest.mark.asyncio
async def test_generate_relationship_analysis_rejects_bare_wrong_literal(
    profile_a, profile_b
) -> None:
    """Grounding-Fix (CRITICAL Security-Finding): a non-mock provider that states a
    numerology fact as a bare literal digit instead of citing it via a
    ``{{metric:a/b:ID}}`` placeholder must be rejected -- even though the pipeline's own
    ``canonical_refs``/``knowledge_refs`` are hardcoded and would otherwise look
    "provenance-covered" regardless of what the LLM actually wrote. The literal here is
    Person B's own real life-path digits, misattributed to Person A -- the exact class
    of fabricated-but-plausible claim the missing grounding mechanism could not catch
    before this fix. Mock output is exempt from this check (see `is_mock_provider` in
    pipeline.py), so this test deliberately reports itself as a non-mock provider."""
    frame = load_relationship_frame(KNOWLEDGE_ROOT, "PARTNER")
    assert frame is not None
    wrong_digits = next(
        digits
        for value in build_metric_display_value_index(profile_b).values()
        for digits in re.findall(r"\d+", value)
        if len(digits) >= 2
    )

    class WrongLiteralProvider:
        async def health(self) -> ProviderHealth:
            return ProviderHealth(
                status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
            )

        async def generate(self, request: GenerationRequest) -> GenerationResult:
            raise AssertionError("not used")

        async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
            text = (
                f"Der Lebenspfad von Person A ist buchstäblich {wrong_digits}, "
                "das prägt dieses Thema."
            )
            return schema(text=text)

    with pytest.raises(AnalysisGenerationError):
        await generate_relationship_analysis(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type="PARTNER",
            frame_knowledge=frame,
            llm=WrongLiteralProvider(),
            knowledge_version="0.1.0",
        )


@pytest.mark.asyncio
async def test_generate_relationship_analysis_resolves_placeholder_to_canonical_value(
    profile_a, profile_b
) -> None:
    """The compliant counterpart to the rejection test above: a provider that cites a
    numeric fact via the required placeholder syntax validates successfully, and the
    final `ThemeStatement.text` carries the resolved canonical value with no leftover
    placeholder syntax."""
    frame = load_relationship_frame(KNOWLEDGE_ROOT, "PARTNER")
    assert frame is not None
    expected_value = build_metric_display_value_index(profile_a)["life_path"]

    class PlaceholderProvider:
        async def health(self) -> ProviderHealth:
            return ProviderHealth(
                status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
            )

        async def generate(self, request: GenerationRequest) -> GenerationResult:
            raise AssertionError("not used")

        async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
            text = (
                "Der Lebenspfad von Person A ({{metric:a:life_path}}) prägt dieses Thema spürbar."
            )
            return schema(text=text)

    result = await generate_relationship_analysis(
        profile_a=profile_a,
        profile_b=profile_b,
        relationship_type="PARTNER",
        frame_knowledge=frame,
        llm=PlaceholderProvider(),
        knowledge_version="0.1.0",
    )
    for dimension in result.dimensions:
        for statement in dimension.statements:
            assert "{{" not in statement.text and "}}" not in statement.text
            assert expected_value in statement.text
