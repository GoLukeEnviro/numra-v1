"""Regression: no LLM-rendered surface may carry internal prompt scaffolding.

PR #98 closed this for the Copilot path only; the relationship-analysis,
shadow-dynamics and report pipelines passed `MockLLMProvider` output through
unchecked, so the request scaffolding (system instructions and `[role:label]`
framed grounding blocks) reached the API response, the DOM and `result_json`.

These tests assert the contract on the *output* of the real pipelines, so they
hold for any provider that ever echoes its own prompt back — not just the mock.
"""

from __future__ import annotations

import datetime as dt
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

#: The complete framing set `MockLLMProvider._compose_text` can emit (one marker per
#: request field / context-block role). Extended only when that set grows.
FORBIDDEN_SCAFFOLDING_MARKERS = (
    "[system]",
    "[profile_fact:",
    "[knowledge:",
    "[instruction_supplement:",
    "[untrusted_user_content:",
    "[user_instructions]",
)

_SCAFFOLDING = "[system] internal prompt text\n[profile_fact:life_path] grounded fact follows\n"

#: The shape a *real* provider leaves behind when it copies a context block's label
#: into its own prose instead of echoing the request: the marker sits inside a
#: sentence, never at the start of a line. Captured from the audit stack on
#: 2026-09-20 (RC2 journey against the real Ollama provider), where the persisted
#: `result_json` carried "... die durch [profile_fact:a:expression] gepraegt ist ...".
#: The line-anchored detector missed it, so the analysis rendered the scaffolding.
_INLINE_SCAFFOLDING = (
    "In der Kommunikation zeigt sich eine strukturierte Ausdrucksweise, die durch "
    "[profile_fact:a:expression] gepraegt ist, waehrend Person B mit "
    "[profile_fact:b:expression] eher grosszuegig zuhoert."
)


@pytest.fixture(scope="module")
def knowledge_base():
    return load_knowledge_base(KNOWLEDGE_ROOT)


@pytest.fixture(scope="module")
def profile_a():
    return calculate_profile(
        PersonInput(
            birth_first_names="Lukas",
            birth_middle_names=None,
            birth_last_name="Springer",
            birth_date=dt.date(1986, 7, 18),
        ),
        as_of_date=dt.date(2026, 8, 19),
    )


@pytest.fixture(scope="module")
def profile_b():
    return calculate_profile(
        PersonInput(
            birth_first_names="Anna",
            birth_middle_names=None,
            birth_last_name="Berger",
            birth_date=dt.date(1990, 3, 14),
        ),
        as_of_date=dt.date(2026, 8, 19),
    )


class _ScaffoldingProvider:
    """Stands in for a real provider that one day returns its own prompt back."""

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        raise AssertionError("not used")

    async def generate_structured(
        self,
        request: StructuredGenerationRequest,
        schema: type,  # type: ignore[no-untyped-def]
    ):
        return schema(text=_SCAFFOLDING)


class _InlineScaffoldingProvider:
    """Stands in for a real provider that copies a context block's label into prose."""

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        raise AssertionError("not used")

    async def generate_structured(
        self,
        request: StructuredGenerationRequest,
        schema: type,  # type: ignore[no-untyped-def]
    ):
        return schema(text=_INLINE_SCAFFOLDING)


async def test_relationship_analysis_mock_text_has_no_prompt_scaffolding(
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

    texts = [
        statement.text for dimension in result.dimensions for statement in dimension.statements
    ]
    assert texts
    for text in texts:
        for marker in FORBIDDEN_SCAFFOLDING_MARKERS:
            assert marker not in text, f"relationship mock text leaked {marker!r}: {text[:120]!r}"


async def test_shadow_dynamics_mock_text_has_no_prompt_scaffolding(
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

    texts = [
        statement.text
        for group in (
            result.user_a_shadow_themes,
            result.user_b_shadow_themes,
            (result.interaction_pattern,),
            (result.escalation_loop,),
            result.deescalation_opportunities,
        )
        for statement in group
    ]
    assert texts
    for text in texts:
        for marker in FORBIDDEN_SCAFFOLDING_MARKERS:
            assert marker not in text, f"shadow mock text leaked {marker!r}: {text[:120]!r}"


async def test_relationship_analysis_fails_closed_on_provider_scaffolding(
    profile_a, profile_b
) -> None:
    """A provider that hands back its own prompt scaffolding must never be rendered
    or persisted as product output — the analysis must fail, not leak."""
    frame = load_relationship_frame(KNOWLEDGE_ROOT, "PARTNER")
    assert frame is not None

    with pytest.raises(AnalysisGenerationError):
        await generate_relationship_analysis(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type="PARTNER",
            frame_knowledge=frame,
            llm=_ScaffoldingProvider(),
            knowledge_version="0.1.0",
        )


async def test_relationship_analysis_fails_closed_on_inline_scaffolding(
    profile_a, profile_b
) -> None:
    """Same contract, but for the shape a real model actually produces: the marker is
    embedded in a sentence rather than starting a line. This is the case that reached
    the UI on the audit stack — the line-anchored detector alone does not cover it."""
    frame = load_relationship_frame(KNOWLEDGE_ROOT, "PARTNER")
    assert frame is not None

    with pytest.raises(AnalysisGenerationError):
        await generate_relationship_analysis(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type="PARTNER",
            frame_knowledge=frame,
            llm=_InlineScaffoldingProvider(),
            knowledge_version="0.1.0",
        )


async def test_shadow_dynamics_fails_closed_on_inline_scaffolding(
    profile_a, profile_b, knowledge_base
) -> None:
    """The shadow-dynamics path shares `_validate_and_resolve_text`; a marker inside a
    sentence must fail it there too."""
    rules = load_shadow_interaction_rules(KNOWLEDGE_ROOT)

    with pytest.raises(AnalysisGenerationError):
        await generate_shadow_dynamics(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type="PARTNER",
            knowledge=knowledge_base,
            shadow_rules=rules,
            llm=_InlineScaffoldingProvider(),
            knowledge_version="0.1.0",
        )
