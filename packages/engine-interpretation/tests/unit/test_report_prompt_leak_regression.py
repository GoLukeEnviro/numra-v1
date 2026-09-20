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

from numra_interpretation.knowledge_loader import load_knowledge_base
from numra_interpretation.llm.mock_provider import MockLLMProvider
from numra_interpretation.llm.types import (
    ContextBlock,
    GenerationRequest,
    GenerationResult,
    ProviderHealth,
    StructuredGenerationRequest,
)
from numra_interpretation.report import build_manifest, generate_report
from numra_interpretation.report.pipeline import (
    ReportGenerationError,
    _mock_sentences,
    _summary_from_text,
)
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

#: The shape a *generative* model leaves behind when it copies a context block's label
#: into its prose instead of echoing the request: the marker sits inside a sentence.
#: Captured on the audit stack on 2026-09-20, where the persisted relationship-analysis
#: text carried "... die durch [profile_fact:a:expression] gepraegt ist ...".
_INLINE_SCAFFOLDING = (
    "Der Ausdruck zeigt sich als strukturierte Sichtweise, die durch "
    "[profile_fact:life_path] gepraegt ist und das grosse Ganze betont."
)


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


class _InlineScaffoldingProvider:
    """A real provider that copies a context block's label into its own sentence."""

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
            return schema(
                text=_INLINE_SCAFFOLDING, numeric_claims=request.numeric_claims, summary="s"
            )
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


async def test_report_mock_sections_have_no_internal_instruction_text(
    sample_profile, knowledge_base
) -> None:
    """The bracket-marker check above is not sufficient on its own.

    The mock section text is seeded from every context block's raw content, which
    includes the `instruction_supplement` blocks — those carry PROMPT INSTRUCTIONS,
    not grounding facts, and they are plain prose with no bracket prefix, so
    `contains_prompt_scaffolding` never matches them. The report therefore shipped
    sentences like "The only valid ids in the metric placeholder namespace are: …"
    (and, for FULL/ULTIMATE, "Target length for this section: …",
    "numeric_claims must include exactly one entry per metric id: …") as product
    text, persisted in `content_json` and rendered by the report reader.

    These exact sentences are what the mock text must not contain; the assertion is
    on the sentences themselves rather than on the block list, so it still holds if
    the instruction wording changes.
    """
    instruction_sentences = (
        "The only valid ids in the metric placeholder namespace are",
        "The only valid ids in the special placeholder namespace are",
        "Never invent an id outside these two lists",
        "Target length for this section",
        "Do not pad with repetition to reach this length",
        "numeric_claims must include exactly one entry per metric id",
        "never the metric-placeholder syntax used in the text field",
    )
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")

    report = await generate_report(
        profile=sample_profile,
        knowledge=knowledge_base,
        manifest=manifest,
        llm=MockLLMProvider(),
    )

    assert report.sections
    for section in report.sections:
        for sentence in instruction_sentences:
            assert sentence not in section.text, (
                f"report section {section.section_id!r} leaked internal instruction "
                f"text {sentence!r}: {section.text[:160]!r}"
            )


async def test_mock_sentences_are_prose_only(sample_profile, knowledge_base) -> None:
    """Der Vertrag der Mock-Textquelle: nur fertige Prosa.

    Frueher zog der Mock seine Saetze aus *jedem* Kontextblock -- inklusive der
    `instruction_supplement`-Bloecke (Prompt-Anweisungen), der
    `untrusted_user_content`-Bloecke (der fremde Tagebucheintrag) und der
    `profile_fact`-Bloecke, die in interner Notation stehen (``Hidden Passion:
    values=[5], frequency=4``, ``Pinnacle 1=8``). Alle drei sind keine Aussagen ueber
    das Profil, und die dritte wurde als Produkttext lesbar wie ein Debug-Dump.

    Der Test prueft deshalb beides: die ausgeschlossenen Rollen kommen nicht vor, UND
    die interne Notation verschwindet (ihre Fakten liefert der Composer als Prosa).
    """
    blocks = (
        ContextBlock(role="profile_fact", label="life_path", content="life_path = 22/4"),
        ContextBlock(role="knowledge", label="life_path", content="Lebenszahl 22/4: Prosa."),
        ContextBlock(
            role="instruction_supplement",
            label="valid_placeholder_ids",
            content="The only valid ids in the metric placeholder namespace are: life_path.",
        ),
        ContextBlock(
            role="instruction_supplement",
            label="word_count_target",
            content="Target length for this section: approximately 136 words.",
        ),
        ContextBlock(role="untrusted_user_content", label="journal", content="user entry text"),
    )
    spec = build_manifest(report_type="QUICK", calculation_id="calc-1").sections[1]

    sentences = _mock_sentences(
        profile=sample_profile, knowledge=knowledge_base, spec=spec, blocks=blocks
    )

    assert sentences, "der Abschnitt braucht Saetze"
    assert "Lebenszahl 22/4: Prosa." in sentences
    for sentence in sentences:
        assert "The only valid ids" not in sentence, sentences
        assert "Target length for this section" not in sentence, sentences
        assert "user entry text" not in sentence, sentences
        # Interne Notation ist kein Produkttext mehr.
        assert "life_path = 22/4" not in sentence, sentences
        assert "=" not in sentence.split("(")[0], sentence


async def test_mock_report_text_carries_no_machine_notation(sample_profile, knowledge_base) -> None:
    """Die vom Audit gefundenen Dump-Muster duerfen in keiner Sektion mehr stehen:
    die `section_id` als erstes Wort, Python-Container-Reprs aus den
    `profile_fact`-Bloecken und die internen Beschriftungen der Zyklus-Bloecke."""
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")

    report = await generate_report(
        profile=sample_profile,
        knowledge=knowledge_base,
        manifest=manifest,
        llm=MockLLMProvider(),
    )

    for section in report.sections:
        assert not section.text.startswith(section.section_id), section.text[:120]
        for machine_notation in ("values=[", "frequency=", "Pinnacle 1=", "Challenge 1="):
            assert machine_notation not in section.text, (
                f"Sektion {section.section_id!r} enthaelt interne Notation "
                f"{machine_notation!r}: {section.text[:160]!r}"
            )
        # Jeder Absatz beginnt mit einem lesbaren Satz, nicht mit einem Bezeichner.
        for paragraph in section.text.split("\n\n"):
            assert paragraph[:1].isupper(), paragraph[:80]
            assert len(paragraph.split()) >= 12, paragraph[:80]


async def test_mock_report_summary_is_product_prose(sample_profile, knowledge_base) -> None:
    """Die Zusammenfassung wird ueber dem Abschnitt gerendert. Sie darf keine interne
    Buchhaltung sein ("<Titel>: 136 words generated.") und keine Platzhalter tragen."""
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")

    report = await generate_report(
        profile=sample_profile,
        knowledge=knowledge_base,
        manifest=manifest,
        llm=MockLLMProvider(),
    )

    assert report.sections
    for section in report.sections:
        assert section.summary.strip(), section.section_id
        assert "words generated" not in section.summary, section.summary
        assert "words targeted" not in section.summary, section.summary
        assert "{{" not in section.summary, section.summary
        assert section.summary == _summary_from_text(section.text), (
            f"Sektion {section.section_id!r}: Zusammenfassung ist nicht der erste Satz "
            f"des Abschnitts"
        )


async def test_report_fails_closed_on_provider_scaffolding(sample_profile, knowledge_base) -> None:
    """A provider returning its own prompt scaffolding must fail generation rather
    than have that scaffolding persisted as report content.

    The failure surfaces as `InvalidReportSection` from the second (repair) attempt:
    the scaffolding is rejected on the first attempt and the retry, after which the
    pipeline propagates — it never falls back to rendering the scaffolding.
    """
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")

    with pytest.raises(ReportGenerationError, match="REPORT_SECTION_UNRENDERABLE"):
        await generate_report(
            profile=sample_profile,
            knowledge=knowledge_base,
            manifest=manifest,
            llm=_ScaffoldingProvider(),
        )


async def test_report_fails_closed_on_inline_provider_scaffolding(
    sample_profile, knowledge_base
) -> None:
    """Same contract for the shape a generative model produces: the block label is
    embedded in the middle of its own sentence instead of starting a line. The detector
    is no longer line-anchored precisely because this shape reached product output on
    the audit stack (relationship analysis, 2026-09-20)."""
    manifest = build_manifest(report_type="QUICK", calculation_id="calc-1")

    with pytest.raises(ReportGenerationError, match="REPORT_SECTION_UNRENDERABLE"):
        await generate_report(
            profile=sample_profile,
            knowledge=knowledge_base,
            manifest=manifest,
            llm=_InlineScaffoldingProvider(),
        )
