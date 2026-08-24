from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from numra_interpretation.errors import InvalidReportSection
from numra_interpretation.knowledge_loader import load_knowledge_base
from numra_interpretation.llm.mock_provider import MockLLMProvider
from numra_interpretation.llm.types import (
    GenerationRequest,
    GenerationResult,
    NumericClaim,
    ProviderHealth,
    StructuredGenerationRequest,
)
from numra_interpretation.llm.validator import build_metric_display_value_index
from numra_interpretation.report import (
    REPORT_TYPE_WORD_RANGES,
    build_manifest,
    generate_report,
    lint_report,
)
from numra_interpretation.report.pipeline import ReportGenerationError
from numra_interpretation.report.schemas import (
    GeneratedSectionContent,
    ReportOutline,
    ReportOutlineEntry,
    StructuredReportSection,
)
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


async def test_generate_report_sections_carry_manifest_provenance(
    sample_profile, knowledge_base
) -> None:
    """V1.5 Epic M: each generated section's metric_refs/knowledge_refs must be
    exactly the manifest's own ReportSectionSpec values -- not re-derived from the
    generated text, not empty just because the mock provider ran."""
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")
    provider = MockLLMProvider()

    report = await generate_report(
        profile=sample_profile, knowledge=knowledge_base, manifest=manifest, llm=provider
    )

    spec_by_id = {spec.section_id: spec for spec in manifest.sections}
    assert len(report.sections) > 0
    for section in report.sections:
        spec = spec_by_id[section.section_id]
        assert section.metric_refs == spec.metric_refs
        assert section.knowledge_refs == spec.knowledge_refs

    # At least one real section actually carries non-empty refs (not a vacuous check).
    assert any(s.metric_refs or s.knowledge_refs for s in report.sections)


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


def _target_length_filler(section_id: str, target_word_count: int) -> str:
    """Section-varying, roughly target-length filler text — same approach as
    `FlakyProvider` above — so a fake provider's output doesn't itself trip the global
    lint's DuplicateParagraphDetection/WordCountValidation checks, which are unrelated
    to whatever this particular fake provider is testing."""
    words = (f"platzhaltertext für {section_id}".split() * (target_word_count // 3 + 1))[
        :target_word_count
    ]
    return " ".join(words)


async def test_generate_report_rejects_bare_numeric_literal_from_real_provider(
    sample_profile, knowledge_base
) -> None:
    """P1 numeric-claim hardening: a non-mock provider that types a profile's own
    numerology value as a bare digit instead of citing it via {{metric:ID}} is
    rejected on the first attempt; a compliant repair attempt then succeeds. Mock
    output is exempt from this check (see pipeline.py's `is_mock_provider` gate) so
    this test deliberately reports itself as a non-mock provider."""
    index = build_metric_display_value_index(sample_profile)
    metric_id, bare_digit = next(
        (mid, d) for mid, value in index.items() for d in re.findall(r"\d+", value) if len(d) >= 2
    )

    class RealFakeProvider:
        async def health(self) -> ProviderHealth:
            return ProviderHealth(
                status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
            )

        async def generate(self, request: GenerationRequest) -> GenerationResult:
            raise AssertionError("not used")

        async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
            section_id = request.metadata["section_id"]
            attempt = request.metadata.get("attempt")
            target = int(request.metadata["target_word_count"])
            filler = _target_length_filler(section_id, target)
            if attempt == "1":
                text = f"Buchstäblich {bare_digit} ohne Platzhalter. {filler}"
            else:
                text = f"Siehe {{{{metric:{metric_id}}}}}. {filler}"
            # Echo the requested claims back (like a well-behaved real provider
            # would) so this fixture's unrelated concern (bare-literal detection)
            # doesn't also trip the metric-ref-coverage check on repair.
            return GeneratedSectionContent(
                title=section_id, text=text, numeric_claims=request.numeric_claims, summary="s"
            )

    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")
    report = await generate_report(
        profile=sample_profile,
        knowledge=knowledge_base,
        manifest=manifest,
        llm=RealFakeProvider(),
    )
    assert len(report.sections) == len(manifest.sections)


async def test_generate_report_bare_literal_on_repair_attempt_also_raises(
    sample_profile, knowledge_base
) -> None:
    """Documents the existing one-repair-attempt limit interacting with the new check:
    if the repair attempt also types a bare literal, the pipeline's single permitted
    repair is already spent, so the raw InvalidReportSection propagates (generate_report
    only wraps the *lint-after-assembly* failure path into ReportGenerationError, not a
    second per-section retry — see pipeline.py's per-section try/except)."""
    index = build_metric_display_value_index(sample_profile)
    bare_digit = next(
        d for value in index.values() for d in re.findall(r"\d+", value) if len(d) >= 2
    )

    class AlwaysBareProvider:
        async def health(self) -> ProviderHealth:
            return ProviderHealth(
                status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
            )

        async def generate(self, request: GenerationRequest) -> GenerationResult:
            raise AssertionError("not used")

        async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
            section_id = request.metadata["section_id"]
            target = int(request.metadata["target_word_count"])
            filler = _target_length_filler(section_id, target)
            text = f"Immer wieder buchstäblich {bare_digit}, nie ein Platzhalter. {filler}"
            return GeneratedSectionContent(
                title=section_id, text=text, numeric_claims=(), summary="s"
            )

    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")
    with pytest.raises(InvalidReportSection):
        await generate_report(
            profile=sample_profile,
            knowledge=knowledge_base,
            manifest=manifest,
            llm=AlwaysBareProvider(),
        )


async def test_generate_report_mock_provider_is_exempt_from_bare_literal_check(
    sample_profile, knowledge_base
) -> None:
    """Sanity check for the exemption itself: MockLLMProvider's deterministic output
    (which echoes raw grounding facts, including bare digits, by design) must not be
    rejected by the unauthorized-literal check."""
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")
    report = await generate_report(
        profile=sample_profile, knowledge=knowledge_base, manifest=manifest, llm=MockLLMProvider()
    )
    assert len(report.sections) == len(manifest.sections)


async def test_generate_report_full_type_runs_outline_step(sample_profile, knowledge_base) -> None:
    """P1: 'a true outline step for FULL/ULTIMATE' — a single upfront
    generate_structured(ReportOutline) call precedes per-section generation, and a
    planned focus it returns is threaded into that section's own context."""
    manifest = build_manifest(report_type="FULL", calculation_id="calc-1")
    schema_calls: list[str] = []
    seen_outline_focus_for: list[str] = []
    first_section_id = manifest.sections[0].section_id

    class OutlineTrackingProvider:
        async def health(self) -> ProviderHealth:
            return ProviderHealth(
                status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
            )

        async def generate(self, request: GenerationRequest) -> GenerationResult:
            raise AssertionError("not used")

        async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
            schema_calls.append(schema.__name__)
            if schema is ReportOutline:
                return ReportOutline(
                    entries=(
                        ReportOutlineEntry(
                            section_id=first_section_id, planned_focus="Betone Klarheit."
                        ),
                    )
                )
            section_id = request.metadata["section_id"]
            target = int(request.metadata["target_word_count"])
            if any(b.label == "outline_focus" for b in request.context_blocks):
                seen_outline_focus_for.append(section_id)
            return GeneratedSectionContent(
                title=section_id,
                text=_target_length_filler(section_id, target),
                numeric_claims=request.numeric_claims,
                summary="s",
            )

    report = await generate_report(
        profile=sample_profile,
        knowledge=knowledge_base,
        manifest=manifest,
        llm=OutlineTrackingProvider(),
    )
    assert schema_calls[0] == "ReportOutline"
    assert seen_outline_focus_for == [first_section_id]
    assert len(report.sections) == len(manifest.sections)


async def test_generate_report_quick_type_skips_outline_step(
    sample_profile, knowledge_base
) -> None:
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")
    schema_calls: list[str] = []

    class TrackingProvider:
        async def health(self) -> ProviderHealth:
            return ProviderHealth(
                status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
            )

        async def generate(self, request: GenerationRequest) -> GenerationResult:
            raise AssertionError("not used")

        async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
            schema_calls.append(schema.__name__)
            section_id = request.metadata["section_id"]
            target = int(request.metadata["target_word_count"])
            return GeneratedSectionContent(
                title=section_id,
                text=_target_length_filler(section_id, target),
                numeric_claims=request.numeric_claims,
                summary="s",
            )

    await generate_report(
        profile=sample_profile, knowledge=knowledge_base, manifest=manifest, llm=TrackingProvider()
    )
    assert "ReportOutline" not in schema_calls


async def test_generate_report_tells_model_the_valid_placeholder_ids(
    sample_profile, knowledge_base
) -> None:
    """Regression test: live against Ollama Cloud's deepseek-v4-pro, the system
    instructions said to reference facts via "a known metric id" without ever
    stating which ids are known, and the model invented a plausible-sounding but
    wrong id (`personality_number` instead of `personality`) that
    `_resolve_placeholders` then rejected. Assert every section's context now
    carries the real, resolvable id list — and never the literal "{{"/"}}"
    placeholder syntax itself, which risks being echoed into MockLLMProvider's
    seeded-from-context-blocks filler text and then misfiring the placeholder
    resolver."""
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")
    seen_blocks: list[tuple] = []

    class TrackingProvider:
        async def health(self) -> ProviderHealth:
            return ProviderHealth(
                status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
            )

        async def generate(self, request: GenerationRequest) -> GenerationResult:
            raise AssertionError("not used")

        async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
            seen_blocks.append(request.context_blocks)
            section_id = request.metadata["section_id"]
            target = int(request.metadata["target_word_count"])
            return GeneratedSectionContent(
                title=section_id,
                text=_target_length_filler(section_id, target),
                numeric_claims=request.numeric_claims,
                summary="s",
            )

    await generate_report(
        profile=sample_profile, knowledge=knowledge_base, manifest=manifest, llm=TrackingProvider()
    )

    for blocks in seen_blocks:
        id_blocks = [b for b in blocks if b.label == "valid_placeholder_ids"]
        assert id_blocks, "expected a valid_placeholder_ids context block for every section"
        content = id_blocks[0].content
        assert "personality" in content
        assert "{{" not in content
        assert "}}" not in content


async def test_generate_report_tells_model_which_numeric_claims_ids_are_mandatory(
    sample_profile, knowledge_base
) -> None:
    """V1.6-C-era production regression test: `request.numeric_claims` (the section's
    required/candidate claim set) is never turned into chat messages by any concrete
    provider -- ollama_provider._build_messages/_build_structured_messages only read
    system_instructions/context_blocks/user_instructions -- so a real model was never
    told which ids its own `numeric_claims` output array had to cover, and every real
    generation since 388bbbb failed post-generation with `InvalidReportSection:
    MissingMetricCoverage`. Assert every section whose spec requires at least one
    metric id now carries an explicit instruction_supplement context block naming
    every one of those ids, so the requirement is something a real provider's prompt
    actually contains -- not just something validate_metric_ref_coverage checks
    after the fact."""
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")
    seen_by_section: dict[str, tuple] = {}

    class TrackingProvider:
        async def health(self) -> ProviderHealth:
            return ProviderHealth(
                status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
            )

        async def generate(self, request: GenerationRequest) -> GenerationResult:
            raise AssertionError("not used")

        async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
            section_id = request.metadata["section_id"]
            seen_by_section[section_id] = request.context_blocks
            target = int(request.metadata["target_word_count"])
            return GeneratedSectionContent(
                title=section_id,
                text=_target_length_filler(section_id, target),
                numeric_claims=request.numeric_claims,
                summary="s",
            )

    await generate_report(
        profile=sample_profile, knowledge=knowledge_base, manifest=manifest, llm=TrackingProvider()
    )

    spec_by_id = {spec.section_id: spec for spec in manifest.sections}
    index = build_metric_display_value_index(sample_profile)
    sections_with_required_ids = 0
    for section_id, blocks in seen_by_section.items():
        spec = spec_by_id[section_id]
        required_ids = tuple(
            mid for mid in (spec.metric_refs or tuple(index.keys())[:3]) if mid in index
        )
        required_blocks = [b for b in blocks if b.label == "required_numeric_claims"]
        if not required_ids:
            assert not required_blocks, f"{section_id} has no required ids but got a block"
            continue
        sections_with_required_ids += 1
        assert required_blocks, f"{section_id} requires {required_ids} but has no instruction"
        content = required_blocks[0].content
        for metric_id in required_ids:
            assert metric_id in content, f"{section_id}: {metric_id!r} missing from {content!r}"

    assert sections_with_required_ids > 0


async def test_generate_report_timing_section_gets_knowledge_grounding(
    sample_profile, knowledge_base
) -> None:
    """V1.6 C regression test: before this fix, the `timing` section's context
    blocks only ever carried a bare `personal_year = 5/5`-style `profile_fact` block
    (via `_generic_metric_block`) because the grounding helper checked
    `CORE_METRIC_IDS` alone. It must now get the same knowledge-composed
    `role="knowledge"` text the eight core metrics already get, reusing
    `compose_section`/`compose_timing_sections` exactly like Epic K's Daily Brief."""
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")
    timing_blocks: list[tuple] = []

    class TrackingProvider:
        async def health(self) -> ProviderHealth:
            return ProviderHealth(
                status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
            )

        async def generate(self, request: GenerationRequest) -> GenerationResult:
            raise AssertionError("not used")

        async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
            section_id = request.metadata["section_id"]
            if section_id == "timing":
                timing_blocks.extend(request.context_blocks)
            target = int(request.metadata["target_word_count"])
            return GeneratedSectionContent(
                title=section_id,
                text=_target_length_filler(section_id, target),
                numeric_claims=request.numeric_claims,
                summary="s",
            )

    await generate_report(
        profile=sample_profile, knowledge=knowledge_base, manifest=manifest, llm=TrackingProvider()
    )

    assert timing_blocks, "expected the timing section to have been generated"
    knowledge_labels = {b.label for b in timing_blocks if b.role == "knowledge"}
    assert knowledge_labels == {"personal_year", "personal_month", "personal_day"}


async def test_generate_report_timing_section_repairs_when_coverage_missing(
    sample_profile, knowledge_base
) -> None:
    """V1.6 C regression test, end-to-end: reproduces the exact production failure
    shape (the timing section's first attempt cites the prior Pinnacles/Challenges
    section's claims instead of its own personal_year/month/day) and shows the
    existing one-repair-attempt mechanism now catches and fixes it, rather than
    silently assembling a report whose timing section never actually covers what its
    manifest spec requires."""
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")

    class TimingConfusedProvider:
        async def health(self) -> ProviderHealth:
            return ProviderHealth(
                status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
            )

        async def generate(self, request: GenerationRequest) -> GenerationResult:
            raise AssertionError("not used")

        async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
            section_id = request.metadata["section_id"]
            attempt = request.metadata.get("attempt")
            target = int(request.metadata["target_word_count"])
            text = _target_length_filler(section_id, target)
            if section_id == "timing" and attempt == "1":
                # Recycles Pinnacles/Challenges-style claims instead of its own.
                claims = (
                    NumericClaim(metric_id="pinnacle_1", display_value="5"),
                    NumericClaim(metric_id="challenge_1", display_value="2"),
                )
            else:
                claims = request.numeric_claims
            return GeneratedSectionContent(
                title=section_id, text=text, numeric_claims=claims, summary="s"
            )

    report = await generate_report(
        profile=sample_profile,
        knowledge=knowledge_base,
        manifest=manifest,
        llm=TimingConfusedProvider(),
    )
    assert len(report.sections) == len(manifest.sections)


async def test_generate_report_timing_section_raises_when_repair_also_fails(
    sample_profile, knowledge_base
) -> None:
    """Companion to the repair test above: if the repair attempt also fails to cover
    personal_year/month/day, the pipeline's single permitted repair is already
    spent and the failure must propagate -- not silently assemble an incomplete
    report."""
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")

    class AlwaysTimingConfusedProvider:
        async def health(self) -> ProviderHealth:
            return ProviderHealth(
                status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
            )

        async def generate(self, request: GenerationRequest) -> GenerationResult:
            raise AssertionError("not used")

        async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
            section_id = request.metadata["section_id"]
            target = int(request.metadata["target_word_count"])
            text = _target_length_filler(section_id, target)
            if section_id == "timing":
                pinnacle_1 = sample_profile.cycles.pinnacles.pinnacle_1.display_value
                claims = (NumericClaim(metric_id="pinnacle_1", display_value=pinnacle_1),)
            else:
                claims = request.numeric_claims
            return GeneratedSectionContent(
                title=section_id, text=text, numeric_claims=claims, summary="s"
            )

    with pytest.raises(InvalidReportSection, match="MissingMetricCoverage"):
        await generate_report(
            profile=sample_profile,
            knowledge=knowledge_base,
            manifest=manifest,
            llm=AlwaysTimingConfusedProvider(),
        )


def test_build_manifest_prompt_version_is_v2() -> None:
    """V1.6 C: the prompt_version was bumped for the timing-report grounding +
    coverage fix -- new reports are distinguishable from ones generated before it.
    Must stay in sync with `numra_api.services.report_service.PROMPT_VERSION`."""
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")
    assert manifest.prompt_version == "numra-report-v2"
