from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from numra_interpretation.knowledge_loader import load_knowledge_base
from numra_interpretation.llm.mock_provider import MockLLMProvider
from numra_interpretation.llm.types import (
    GenerationRequest,
    GenerationResult,
    NumericClaim,
    ProviderHealth,
    StructuredGenerationRequest,
)
from numra_interpretation.report import (
    REPORT_TYPE_WORD_RANGES,
    build_manifest,
    generate_report,
    lint_report,
)
from numra_interpretation.report.pipeline import ReportGenerationError
from numra_interpretation.report.schemas import GeneratedSectionContent, StructuredReportSection
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[4]
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"


@pytest.fixture(scope="module")
def knowledge_base():
    return load_knowledge_base(KNOWLEDGE_ROOT)


@pytest.fixture(scope="module")
def sample_profile():
    person = PersonInput(
        birth_first_names="Anna",
        birth_middle_names="Marie",
        birth_last_name="Berger",
        birth_date=dt.date(1990, 3, 14),
    )
    return calculate_profile(person, as_of_date=dt.date(2026, 8, 19))


@pytest.mark.parametrize("report_type", ["QUICK", "FULL", "ULTIMATE"])
def test_build_manifest_word_ranges(report_type) -> None:
    manifest = build_manifest(report_type=report_type, calculation_id="calc-1")
    low, high = REPORT_TYPE_WORD_RANGES[report_type]
    assert low <= manifest.total_target_words <= high
    assert len(manifest.sections) >= 10
    section_ids = [s.section_id for s in manifest.sections]
    assert len(section_ids) == len(set(section_ids))


def test_build_manifest_custom_requires_target() -> None:
    with pytest.raises(ValueError):
        build_manifest(report_type="CUSTOM", calculation_id="calc-1")


async def test_generate_report_quick_all_sections_present(sample_profile, knowledge_base) -> None:
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")
    provider = MockLLMProvider()

    report = await generate_report(
        profile=sample_profile, knowledge=knowledge_base, manifest=manifest, llm=provider
    )

    expected_ids = {s.section_id for s in manifest.sections}
    actual_ids = {s.section_id for s in report.sections}
    assert expected_ids == actual_ids
    assert report.model_provider == "mock"


async def test_generate_report_ultimate_reaches_target_scale(
    sample_profile, knowledge_base
) -> None:
    """Master prompt §113 gate: 15,000+ word report generation succeeds with the mock
    provider. This proves the pipeline mechanics (manifest -> per-section grounding ->
    generation -> lint -> assembly) scale to ULTIMATE, not that mock text is genuine
    prose — see specs/evidence/phase-4.md."""
    manifest = build_manifest(report_type="ULTIMATE", calculation_id="calc-1")
    provider = MockLLMProvider()

    report = await generate_report(
        profile=sample_profile, knowledge=knowledge_base, manifest=manifest, llm=provider
    )

    assert report.total_word_count >= 15_000
    assert len(report.sections) == len(manifest.sections)


async def test_generate_report_no_core_number_mutation(sample_profile, knowledge_base) -> None:
    before = sample_profile.model_dump(mode="json")
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")
    await generate_report(
        profile=sample_profile, knowledge=knowledge_base, manifest=manifest, llm=MockLLMProvider()
    )
    after = sample_profile.model_dump(mode="json")
    assert before == after


async def test_generate_report_unavailable_provider_raises(sample_profile, knowledge_base) -> None:
    class UnavailableProvider:
        async def health(self) -> ProviderHealth:
            return ProviderHealth(
                status="unavailable", provider="fake", checked_at=dt.datetime.now(dt.UTC)
            )

        async def generate(self, request: GenerationRequest) -> GenerationResult:
            raise AssertionError("should not be called")

        async def generate_structured(self, request, schema):  # type: ignore[no-untyped-def]
            raise AssertionError("should not be called")

    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")
    with pytest.raises(ReportGenerationError, match="LLM_UNAVAILABLE"):
        await generate_report(
            profile=sample_profile,
            knowledge=knowledge_base,
            manifest=manifest,
            llm=UnavailableProvider(),
        )


async def test_generate_report_repairs_once_then_succeeds(sample_profile, knowledge_base) -> None:
    """First attempt for every section returns a WRONG numeric claim (invalid); the
    pipeline's one permitted repair attempt then gets a correct claim and succeeds."""

    class FlakyProvider:
        async def health(self) -> ProviderHealth:
            return ProviderHealth(
                status="healthy", provider="flaky", checked_at=dt.datetime.now(dt.UTC)
            )

        async def generate(self, request: GenerationRequest) -> GenerationResult:
            raise AssertionError("not used")

        async def generate_structured(
            self, request: StructuredGenerationRequest, schema: type
        ) -> GeneratedSectionContent:
            attempt = request.metadata.get("attempt")
            claims = request.numeric_claims
            section_id = request.metadata["section_id"]
            target = int(request.metadata["target_word_count"])
            words = (f"placeholder text for {section_id}".split() * (target // 4 + 1))[:target]
            unique_text = " ".join(words)
            if attempt == "1" and claims:
                # Deliberately wrong claim on the first attempt for every section.
                bad_claim = NumericClaim(metric_id=claims[0].metric_id, display_value="0/0")
                return GeneratedSectionContent(
                    title=section_id,
                    text=unique_text,
                    numeric_claims=(bad_claim,),
                    summary="draft",
                )
            # Second attempt: correct.
            return GeneratedSectionContent(
                title=section_id,
                text=unique_text,
                numeric_claims=claims,
                summary="repaired",
            )

    manifest = build_manifest(
        report_type="CUSTOM", calculation_id="calc-1", custom_total_target_words=200
    )
    report = await generate_report(
        profile=sample_profile, knowledge=knowledge_base, manifest=manifest, llm=FlakyProvider()
    )
    assert len(report.sections) == len(manifest.sections)


def test_lint_report_detects_missing_section(sample_profile) -> None:
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")
    sections = tuple(
        StructuredReportSection(
            section_id=spec.section_id,
            title=spec.title,
            order_index=spec.order_index,
            text="x " * 50,
            word_count=50,
            summary="s",
        )
        for spec in manifest.sections[:-1]  # drop the last section
    )
    result = lint_report(manifest, sections, sample_profile)
    assert not result.is_valid
    assert any("MissingSections" in e for e in result.errors)


def test_lint_report_detects_unresolved_placeholder(sample_profile) -> None:
    manifest = build_manifest(
        report_type="CUSTOM", calculation_id="calc-1", custom_total_target_words=100
    )
    sections = tuple(
        StructuredReportSection(
            section_id=spec.section_id,
            title=spec.title,
            order_index=spec.order_index,
            text="unresolved {{metric:life_path}} " * 5,
            word_count=15,
            summary="s",
        )
        for spec in manifest.sections
    )
    result = lint_report(manifest, sections, sample_profile)
    assert not result.is_valid
    assert any("PlaceholderResolution" in e for e in result.errors)


def test_lint_report_detects_unsupported_claim(sample_profile) -> None:
    manifest = build_manifest(
        report_type="CUSTOM", calculation_id="calc-1", custom_total_target_words=100
    )
    sections = tuple(
        StructuredReportSection(
            section_id=spec.section_id,
            title=spec.title,
            order_index=spec.order_index,
            text=("Dies ist wissenschaftlich bewiesen. " * 5),
            word_count=25,
            summary="s",
        )
        for spec in manifest.sections
    )
    result = lint_report(manifest, sections, sample_profile)
    assert not result.is_valid
    assert any("UnsupportedClaims" in e for e in result.errors)


def test_lint_report_detects_duplicate_headings(sample_profile) -> None:
    manifest = build_manifest(
        report_type="CUSTOM", calculation_id="calc-1", custom_total_target_words=100
    )
    sections = tuple(
        StructuredReportSection(
            section_id=spec.section_id,
            title="Same Title",
            order_index=spec.order_index,
            text="x " * 20,
            word_count=20,
            summary="s",
        )
        for spec in manifest.sections
    )
    result = lint_report(manifest, sections, sample_profile)
    assert not result.is_valid
    assert any("DuplicateHeadings" in e for e in result.errors)
