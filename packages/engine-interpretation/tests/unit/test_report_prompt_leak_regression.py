"""Regression: generated report sections must never carry internal prompt scaffolding.

The report pipeline exempts `MockLLMProvider` from the unauthorized-literal check
because its deterministic filler echoes raw grounding facts by design. That
exemption was never paired with a guard on the *framing* the same provider emits
(`[system]` and `[role:label]` block prefixes), so mock-generated sections — which
the API persists as `report_sections` and serves to the client — contained the
request scaffolding verbatim.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from numra_interpretation.errors import InvalidReportSection
from numra_interpretation.knowledge_loader import load_knowledge_base
from numra_interpretation.llm.mock_provider import MockLLMProvider
from numra_interpretation.llm.types import (
    GenerationRequest,
    GenerationResult,
    ProviderHealth,
    StructuredGenerationRequest,
)
from numra_interpretation.report import build_manifest, generate_report
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[4]
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"

#: Same framing set as the relationship-pipeline regression: every prefix
#: `MockLLMProvider._compose_text` can emit.
FORBIDDEN_SCAFFOLDING_MARKERS = (
    "[system]",
    "[profile_fact:",
    "[knowledge:",
    "[instruction_supplement:",
    "[untrusted_user_content:",
    "[user_instructions]",
)

_SCAFFOLDING = "[system] internal prompt text\n[profile_fact:life_path] grounded fact follows\n"


@pytest.fixture(scope="module")
def knowledge_base():
    return load_knowledge_base(KNOWLEDGE_ROOT)


@pytest.fixture(scope="module")
def sample_profile():
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
    """A real provider that one day hands its own prompt scaffolding back."""

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
        from numra_interpretation.report.schemas import GeneratedSectionContent

        if schema is GeneratedSectionContent:
            return schema(text=_SCAFFOLDING, numeric_claims=request.numeric_claims, summary="s")
        # The outline step accepts an empty outline from a provider that cannot fill it.
        return schema()


async def test_report_mock_sections_have_no_prompt_scaffolding(
    sample_profile, knowledge_base
) -> None:
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")

    report = await generate_report(
        profile=sample_profile,
        knowledge=knowledge_base,
        manifest=manifest,
        llm=MockLLMProvider(),
    )

    assert report.sections
    for section in report.sections:
        for marker in FORBIDDEN_SCAFFOLDING_MARKERS:
            assert marker not in section.text, (
                f"report section {section.section_id!r} leaked {marker!r}: {section.text[:120]!r}"
            )


async def test_report_fails_closed_on_provider_scaffolding(sample_profile, knowledge_base) -> None:
    """A provider returning its own prompt scaffolding must fail generation rather
    than have that scaffolding persisted as report content.

    The failure surfaces as `InvalidReportSection` from the second (repair) attempt:
    the scaffolding is rejected on the first attempt and the retry, after which the
    pipeline propagates — it never falls back to rendering the scaffolding.
    """
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")

    with pytest.raises(InvalidReportSection, match="PromptScaffoldingRejected"):
        await generate_report(
            profile=sample_profile,
            knowledge=knowledge_base,
            manifest=manifest,
            llm=_ScaffoldingProvider(),
        )
