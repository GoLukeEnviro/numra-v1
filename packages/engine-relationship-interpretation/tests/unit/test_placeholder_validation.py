"""Regression (Befund F08): malformed relationship placeholders must never survive.

`{{a:life_path}}` (missing namespace) and `[metric:a:life_path]` (wrong brackets) used to
pass `_validate_and_resolve_text` unchanged and reached the persisted analysis prose.
They are now rejected fail-closed, so the caller's one-repair-attempt / FAILED logic
applies; the correct `{{metric:a:life_path}}` form keeps resolving.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from numra_interpretation.llm.types import (
    GenerationRequest,
    GenerationResult,
    ProviderHealth,
    StructuredGenerationRequest,
)
from numra_interpretation.llm.validator import build_metric_display_value_index
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput
from numra_relationship_interpretation.errors import AnalysisGenerationError, InvalidAnalysisSection
from numra_relationship_interpretation.knowledge_loader import load_relationship_frame
from numra_relationship_interpretation.pipeline import (
    _validate_and_resolve_text,
    generate_relationship_analysis,
)

pytestmark = pytest.mark.unit

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[4] / "knowledge"

MALFORMED_TEXTS = (
    "Dein Wert ist {{a:life_path}}.",
    "Dein Wert ist {{b:expression}}.",
    "Dein Wert ist [metric:a:life_path].",
    "Dein Wert ist [metric:b:soul_urge].",
    "Dein Wert ist [special:a:hidden_passion].",
    "Dein Wert ist {{metric:a:life_path} offen.",
    "Dein Wert ist {metric:a:life_path}}.",
    "Gemischt {{metric:a:life_path}} und {{b:life_path}}.",
    "Gemischt {{metric:a:life_path}} und [metric:b:life_path].",
)


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


@pytest.mark.parametrize("is_mock_provider", [False, True])
@pytest.mark.parametrize("text", MALFORMED_TEXTS)
def test_malformed_placeholder_is_rejected(text, is_mock_provider, profile_a, profile_b) -> None:
    with pytest.raises(InvalidAnalysisSection, match="MalformedPlaceholder"):
        _validate_and_resolve_text(
            text, profile_a=profile_a, profile_b=profile_b, is_mock_provider=is_mock_provider
        )


def test_correct_placeholder_still_resolves(profile_a, profile_b) -> None:
    expected = build_metric_display_value_index(profile_a)["life_path"]
    resolved = _validate_and_resolve_text(
        "Dein Wert ist {{metric:a:life_path}}.",
        profile_a=profile_a,
        profile_b=profile_b,
        is_mock_provider=False,
    )
    assert resolved == f"Dein Wert ist {expected}."


def test_text_without_markers_is_untouched(profile_a, profile_b) -> None:
    text = "Eine Aussage ohne jede Zahl, nur mit [eckigen] Klammern."
    assert (
        _validate_and_resolve_text(
            text, profile_a=profile_a, profile_b=profile_b, is_mock_provider=False
        )
        == text
    )


class _SequenceProvider:
    """Returns the given texts in order, repeating the last one."""

    def __init__(self, *texts: str) -> None:
        self._texts = texts
        self.calls = 0

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        raise AssertionError("not used")

    async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
        text = self._texts[min(self.calls, len(self._texts) - 1)]
        self.calls += 1
        return schema(text=text)


@pytest.mark.asyncio
async def test_pipeline_fails_when_provider_keeps_emitting_malformed_placeholder(
    profile_a, profile_b
) -> None:
    frame = load_relationship_frame(KNOWLEDGE_ROOT, "PARTNER")
    assert frame is not None
    with pytest.raises(AnalysisGenerationError):
        await generate_relationship_analysis(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type="PARTNER",
            frame_knowledge=frame,
            llm=_SequenceProvider("Dein Wert ist {{a:life_path}}."),
            knowledge_version="0.1.0",
        )


@pytest.mark.asyncio
async def test_pipeline_repairs_via_retry_after_one_malformed_attempt(profile_a, profile_b) -> None:
    frame = load_relationship_frame(KNOWLEDGE_ROOT, "PARTNER")
    assert frame is not None
    expected = build_metric_display_value_index(profile_a)["life_path"]
    provider = _SequenceProvider(
        "Dein Wert ist [metric:a:life_path].",
        "Dein Wert ist {{metric:a:life_path}}.",
    )
    result = await generate_relationship_analysis(
        profile_a=profile_a,
        profile_b=profile_b,
        relationship_type="PARTNER",
        frame_knowledge=frame,
        llm=provider,
        knowledge_version="0.1.0",
    )
    assert provider.calls > 1
    for dimension in result.dimensions:
        for statement in dimension.statements:
            assert "[metric:" not in statement.text and "{{" not in statement.text
    assert any(expected in s.text for d in result.dimensions for s in d.statements)
