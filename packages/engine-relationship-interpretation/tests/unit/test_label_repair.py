"""Regression: Kontextblock-Labels, die das Modell in den Text schreibt, werden
deterministisch aufgeloest (eindeutig) oder fail-closed abgelehnt (mehrdeutig/unbekannt).

Ursache (Audit 2026-09-20): Der Prompt rahmt jeden Fakt als ``[profile_fact:a:expression]``;
ein generatives Modell kopiert das Label in seinen Satz. `rendering_guard` lehnt das
bewusst ab -> die ganze Analyse schlug fehl. Eindeutige Labels verweisen auf genau einen
Fakt des Prompts und werden jetzt auf dessen kanonischen Wert aufgeloest; alles andere
bleibt abgelehnt, der Guard bleibt unveraendert streng.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from numra_interpretation.knowledge_loader import load_knowledge_base
from numra_interpretation.llm.rendering_guard import contains_prompt_scaffolding
from numra_interpretation.llm.types import (
    ContextBlock,
    GenerationRequest,
    GenerationResult,
    ProviderHealth,
    StructuredGenerationRequest,
)
from numra_interpretation.llm.validator import build_metric_display_value_index
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput
from numra_relationship_interpretation import pipeline
from numra_relationship_interpretation.errors import AnalysisGenerationError, InvalidAnalysisSection
from numra_relationship_interpretation.knowledge_loader import (
    load_relationship_frame,
    load_shadow_interaction_rules,
)
from numra_relationship_interpretation.pipeline import (
    _repair_profile_fact_labels,
    _validate_and_resolve_text,
    generate_relationship_analysis,
    generate_shadow_dynamics,
)

pytestmark = pytest.mark.unit

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[4] / "knowledge"


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


@pytest.fixture(scope="module")
def blocks_ab(profile_a, profile_b) -> tuple[ContextBlock, ...]:
    """The profile_fact blocks a relationship request carries: both persons."""
    blocks: list[ContextBlock] = []
    for prefix, profile in (("a", profile_a), ("b", profile_b)):
        for metric_id, value in sorted(build_metric_display_value_index(profile).items()):
            blocks.append(
                ContextBlock(
                    role="profile_fact",
                    label=f"{prefix}:{metric_id}",
                    content=f"{metric_id} = {value}",
                )
            )
    return tuple(blocks)


@pytest.fixture(scope="module")
def blocks_a_only(blocks_ab) -> tuple[ContextBlock, ...]:
    return tuple(b for b in blocks_ab if b.label.startswith("a:"))


# --------------------------------------------------------------------------- repair unit


def test_unique_label_is_rewritten_to_the_sanctioned_placeholder(blocks_ab) -> None:
    repaired = _repair_profile_fact_labels(
        "Gepraegt durch [profile_fact:a:expression] im Alltag.", blocks_ab
    )
    assert repaired == "Gepraegt durch {{metric:a:expression}} im Alltag."


def test_several_labels_of_both_persons_are_all_rewritten(blocks_ab) -> None:
    repaired = _repair_profile_fact_labels(
        "[profile_fact:a:expression] trifft [profile_fact:b:expression], "
        "wieder [profile_fact:a:expression].",
        blocks_ab,
    )
    assert repaired == (
        "{{metric:a:expression}} trifft {{metric:b:expression}}, wieder {{metric:a:expression}}."
    )


def test_label_inside_a_quotation_is_still_resolved(blocks_ab) -> None:
    repaired = _repair_profile_fact_labels(
        'Er nannte es "[profile_fact:b:life_path]" und blieb dabei.', blocks_ab
    )
    assert repaired == 'Er nannte es "{{metric:b:life_path}}" und blieb dabei.'


@pytest.mark.parametrize(
    "text",
    (
        "Ohne Person: [profile_fact:life_path] ist mehrdeutig.",
        "Unbekannte Metrik: [profile_fact:a:does_not_exist].",
        "Fremde Person: [profile_fact:c:life_path].",
        "Mit Leerraum: [profile_fact: a:life_path].",
        "Mit Zusatz: [profile_fact:a:life_path = 5].",
        "Grossgeschrieben: [Profile_Fact:a:life_path].",
    ),
)
def test_ambiguous_or_unknown_labels_are_left_untouched(text, blocks_ab) -> None:
    assert _repair_profile_fact_labels(text, blocks_ab) == text


def test_label_of_a_fact_that_was_not_in_the_prompt_is_not_resolved(blocks_a_only) -> None:
    text = "Person B: [profile_fact:b:life_path]."
    assert _repair_profile_fact_labels(text, blocks_a_only) == text


def test_nested_label_resolves_only_the_inner_reference(blocks_ab) -> None:
    repaired = _repair_profile_fact_labels("[profile_fact:[profile_fact:a:life_path]]", blocks_ab)
    assert repaired == "[profile_fact:{{metric:a:life_path}}]"
    assert contains_prompt_scaffolding(repaired)


@pytest.mark.parametrize(
    "text",
    (
        "Wissen: [knowledge:communication:semantic_context] steht hier.",
        "Anweisung: [instruction_supplement:valid_placeholder_ids] steht hier.",
        "Rahmung: [system] steht hier.",
        "Fremdtext: [untrusted_user_content:note] steht hier.",
    ),
)
def test_only_profile_fact_labels_are_ever_repaired(text, blocks_ab) -> None:
    assert _repair_profile_fact_labels(text, blocks_ab) == text


def test_a_label_naming_a_non_fact_block_is_not_resolved(blocks_ab) -> None:
    """`communication:semantic_context` is a knowledge block's label: borrowing the
    `profile_fact` framing for it must not turn it into a metric reference."""
    blocks = (
        *blocks_ab,
        ContextBlock(role="knowledge", label="communication:semantic_context", content="Text"),
        ContextBlock(role="instruction_supplement", label="valid_placeholder_ids", content="x"),
    )
    for label in ("communication:semantic_context", "valid_placeholder_ids"):
        text = f"Falsch gerahmt: [profile_fact:{label}] im Satz."
        assert _repair_profile_fact_labels(text, blocks) == text


# --------------------------------------------------------------------------- guard bleibt


@pytest.mark.parametrize(
    "marker",
    (
        "[system]",
        "[profile_fact:a:expression]",
        "[knowledge:x]",
        "[instruction_supplement:y]",
        "[untrusted_user_content:z]",
        "[user_instructions]",
    ),
)
def test_guard_still_rejects_every_marker(marker) -> None:
    assert contains_prompt_scaffolding(f"Satz mit {marker} mittendrin.")


@pytest.mark.parametrize(
    "text",
    (
        "Wissen [knowledge:communication:semantic_context] im Satz.",
        "Rahmung [system] im Satz.",
        "Mehrdeutig [profile_fact:life_path] im Satz.",
        "Unbekannt [profile_fact:a:does_not_exist] im Satz.",
        "Verschachtelt [profile_fact:[profile_fact:a:life_path]] im Satz.",
    ),
)
@pytest.mark.parametrize("is_mock_provider", [False, True])
def test_unrepaired_labels_are_still_rejected_by_the_validation_gate(
    text, is_mock_provider, profile_a, profile_b
) -> None:
    with pytest.raises(InvalidAnalysisSection, match="PromptScaffoldingRejected"):
        _validate_and_resolve_text(
            text, profile_a=profile_a, profile_b=profile_b, is_mock_provider=is_mock_provider
        )


@pytest.mark.parametrize(
    "text",
    (
        "Hallo {partner_a}, schoen.",
        "Hallo {{partner_a}}, schoen.",
        "Hallo <partner_a>, schoen.",
        "Hallo %(partner_a)s, schoen.",
        "Hallo {metric:a:life_path}.",
        "Grossgeschrieben [Profile_Fact:a:life_path] im Satz.",
        "Mit Leerraum [ profile_fact:a:life_path ] im Satz.",
        "Mit Leerraum [ KNOWLEDGE:x ] im Satz.",
    ),
)
def test_other_unresolved_template_tokens_are_rejected(text, profile_a, profile_b) -> None:
    with pytest.raises(InvalidAnalysisSection):
        _validate_and_resolve_text(
            text, profile_a=profile_a, profile_b=profile_b, is_mock_provider=False
        )


# --------------------------------------------------------------------------- Unicode

_LOOKALIKES = (
    "Voll\uff3bprofile_fact\uff1aa:expression\uff3d im Satz.",  # full-width [ : ]
    "Voll [profile_fact\uff1aa:expression] im Satz.",  # nur Doppelpunkt
    "Homoglyph [\u0440rofile_fact:a:expression] im Satz.",  # kyrillisch r
    "Homoglyph [kn\u043ewledge:x] im Satz.",  # kyrillisch o
    "Homoglyph [syst\u0435m] im Satz.",  # kyrillisch e
    "Zero-Width [profile\u200b_fact:a:expression] im Satz.",
    "Gemischt \uff3bkn\u043ewledge\uff1ax\uff3d im Satz.",
    "Gross [\u0405ystem] im Satz.",  # kyrillisch S (Grossbuchstabe)
    "Gross [\u041aNOWLEDGE:x] im Satz.",  # kyrillisch K (Grossbuchstabe)
    "Gemischt [\u0405\u0443\u0455t\u0435m] im Satz.",  # Ѕуѕtеm
    "Combining [prof\u0301ile_fact:a] im Satz.",  # U+0301 im Rollennamen
    "Combining [prof\u034file_fact:a] im Satz.",  # U+034F (Mn) im Rollennamen
    "Combining [profile_fact\u0301:a:x] im Satz.",  # vor dem Doppelpunkt
    "Combining [profile_fact:\u0301a:x] im Satz.",  # hinter dem Doppelpunkt
    "Combining [sys\u0301tem] im Satz.",
    "Combining [\u0301system] im Satz.",  # direkt hinter der Klammer
    "Combining [system\u0301] im Satz.",  # vor der schliessenden Klammer
    "Combining [user_instructions\u0301] im Satz.",
    "Combining {\u0301metric:a:life_path} im Satz.",
    "Combining [\u0301metric:a:life_path] im Satz.",
    "Kombi [\u041aNOWLEDGE\u0301:x] im Satz.",  # Gross + Combining
    "Voll {metric:a:life_path} im Satz.".replace("{", "\uff5b").replace("}", "\uff5d"),
    "Voll \uff5b\uff5bpartner_a\uff5d\uff5d im Satz.",
)


@pytest.mark.parametrize("text", _LOOKALIKES)
@pytest.mark.parametrize("is_mock_provider", [False, True])
def test_unicode_lookalike_tokens_are_rejected(
    text, is_mock_provider, profile_a, profile_b
) -> None:
    with pytest.raises(InvalidAnalysisSection):
        _validate_and_resolve_text(
            text, profile_a=profile_a, profile_b=profile_b, is_mock_provider=is_mock_provider
        )


@pytest.mark.parametrize("text", _LOOKALIKES)
async def test_unicode_lookalike_in_a_whole_analysis_fails_closed(
    text, profile_a, profile_b
) -> None:
    frame = load_relationship_frame(KNOWLEDGE_ROOT, "PARTNER")
    assert frame is not None
    with pytest.raises(AnalysisGenerationError):
        await generate_relationship_analysis(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type="PARTNER",
            frame_knowledge=frame,
            llm=_FixedTextProvider(text),
            knowledge_version="0.1.0",
        )


@pytest.mark.parametrize("text", _LOOKALIKES)
def test_lookalike_tokens_are_rejected_by_the_final_backstop(text) -> None:
    with pytest.raises(AnalysisGenerationError, match="ANALYSIS_VALIDATION_FAILED"):
        pipeline._assert_no_unresolved_tokens([text])


@pytest.mark.parametrize("text", _LOOKALIKES)
def test_lookalike_labels_are_never_repaired(text, blocks_ab) -> None:
    assert _repair_profile_fact_labels(text, blocks_ab) == text


def test_check_form_is_linear_in_the_input_length() -> None:
    import time

    sample = "Über José: [Anmerkung] \u0405ystem pro\u0301file straße. " * 22_000  # ~1 Mio.
    assert len(sample) > 1_000_000
    start = time.perf_counter()
    pipeline._canonical_for_check(sample)
    assert time.perf_counter() - start < 5.0


_GERMAN_PROSE = (
    "Über Grenzen hinweg: „Nähe“ und »Freiraum« sind für beide wichtig – größer, schöner, "
    "behutsamer. Straße, Maß, Äußerung, Ärger, Öl und Übung; 25/7 … fast 100 % ehrlich.",
    "Он сказал «да» (русский текст ist kein Marker), und α, β, γ bleiben erlaubt.",
    "Klammern (wie hier) und [Anmerkung der Redaktion] sind normale Prosa.",
    "Gespräch mit José, Zoë und Renée: „Café“ und \u201eNaïve Künstler\u201c, ‚Fjörd‘ – fertig.",
    "Decomposed Jose\u0301 und Zoe\u0308: [Anmerkung der Redaktion, Jose\u0301].",
    "Ѕtraße und КОНТАКТ: Großbuchstaben bleiben Prosa, ebenso ΣΟΦΙΑ und İstanbul.",
)


@pytest.mark.parametrize("text", _GERMAN_PROSE)
def test_ordinary_german_prose_is_not_a_false_positive(text, profile_a, profile_b) -> None:
    resolved = _validate_and_resolve_text(
        text, profile_a=profile_a, profile_b=profile_b, is_mock_provider=True
    )
    assert resolved == text  # geprueft, nie umgeschrieben
    pipeline._assert_no_unresolved_tokens([text])


# --------------------------------------------------------------------------- Pipeline


class _LabelCitingProvider:
    """A real (non-mock) provider that cites the first profile_fact block of each request
    the way the audit model did: by copying its bracketed label into a sentence."""

    def __init__(
        self, template: str = "Das ist gepraegt durch [profile_fact:{label}] im Alltag."
    ) -> None:
        self.template = template
        self.requests: list[StructuredGenerationRequest] = []

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        raise AssertionError("not used")

    async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        label = next(b.label for b in request.context_blocks if b.role == "profile_fact")
        return schema(text=self.template.format(label=label))


class _FixedTextProvider(_LabelCitingProvider):
    def __init__(self, text: str) -> None:
        super().__init__(text)

    async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        return schema(text=self.template)


def _relationship_texts(result) -> list[str]:
    return [s.text for d in result.dimensions for s in d.statements]


def _shadow_texts(result) -> list[str]:
    return [
        s.text
        for group in (
            result.user_a_shadow_themes,
            result.user_b_shadow_themes,
            (result.interaction_pattern,),
            (result.escalation_loop,),
            result.deescalation_opportunities,
        )
        for s in group
    ]


async def test_relationship_analysis_resolves_cited_labels_to_the_canonical_value(
    profile_a, profile_b
) -> None:
    frame = load_relationship_frame(KNOWLEDGE_ROOT, "PARTNER")
    assert frame is not None
    llm = _LabelCitingProvider()

    result = await generate_relationship_analysis(
        profile_a=profile_a,
        profile_b=profile_b,
        relationship_type="PARTNER",
        frame_knowledge=frame,
        llm=llm,
        knowledge_version="0.1.0",
    )

    first_label = next(b.label for b in llm.requests[0].context_blocks if b.role == "profile_fact")
    prefix, metric_id = first_label.split(":")
    profile = profile_a if prefix == "a" else profile_b
    expected = build_metric_display_value_index(profile)[metric_id]
    texts = _relationship_texts(result)
    assert len(texts) == len(frame.dimensions)
    for text in texts:
        assert text == f"Das ist gepraegt durch {expected} im Alltag."
        assert "[" not in text and "{" not in text
    assert len(llm.requests) == len(frame.dimensions)  # kein Wiederholungsversuch noetig


async def test_shadow_dynamics_resolves_labels_for_every_component(profile_a, profile_b) -> None:
    llm = _LabelCitingProvider()

    result = await generate_shadow_dynamics(
        profile_a=profile_a,
        profile_b=profile_b,
        relationship_type="PARTNER",
        knowledge=load_knowledge_base(KNOWLEDGE_ROOT),
        shadow_rules=load_shadow_interaction_rules(KNOWLEDGE_ROOT),
        llm=llm,
        knowledge_version="0.1.0",
    )

    texts = _shadow_texts(result)
    assert len(texts) == 5
    for text in texts:
        assert "[" not in text and "{" not in text
        assert not contains_prompt_scaffolding(text)


@pytest.mark.parametrize(
    "text",
    (
        "Wissen [knowledge:communication:semantic_context] im Satz.",
        "Mehrdeutig [profile_fact:life_path] im Satz.",
        "Unbekannt [profile_fact:a:does_not_exist] im Satz.",
        "Verschachtelt [profile_fact:[profile_fact:a:life_path]] im Satz.",
        "Template {partner_a} im Satz.",
    ),
)
async def test_unrepairable_output_fails_the_analysis_with_one_error_class(
    text, profile_a, profile_b
) -> None:
    frame = load_relationship_frame(KNOWLEDGE_ROOT, "PARTNER")
    assert frame is not None

    with pytest.raises(AnalysisGenerationError, match="ANALYSIS_VALIDATION_FAILED"):
        await generate_relationship_analysis(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type="PARTNER",
            frame_knowledge=frame,
            llm=_FixedTextProvider(text),
            knowledge_version="0.1.0",
        )

    with pytest.raises(AnalysisGenerationError, match="ANALYSIS_VALIDATION_FAILED"):
        await generate_shadow_dynamics(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type="PARTNER",
            knowledge=load_knowledge_base(KNOWLEDGE_ROOT),
            shadow_rules=load_shadow_interaction_rules(KNOWLEDGE_ROOT),
            llm=_FixedTextProvider(text),
            knowledge_version="0.1.0",
        )


async def test_label_of_the_other_person_is_not_resolved_in_a_single_person_component(
    profile_a, profile_b
) -> None:
    """`user_a_shadow_theme` only sends A's facts; B's label was never in that prompt."""
    with pytest.raises(AnalysisGenerationError):
        await generate_shadow_dynamics(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type="PARTNER",
            knowledge=load_knowledge_base(KNOWLEDGE_ROOT),
            shadow_rules=load_shadow_interaction_rules(KNOWLEDGE_ROOT),
            llm=_FixedTextProvider("Fremd: [profile_fact:b:life_path] im Satz."),
            knowledge_version="0.1.0",
        )


async def test_result_level_backstop_rejects_a_token_that_slipped_past_the_statements(
    profile_a, profile_b, monkeypatch
) -> None:
    monkeypatch.setattr(
        pipeline, "_recommended_micro_tasks", lambda _ctx: ("Aufgabe fuer {partner_a}.",)
    )
    with pytest.raises(AnalysisGenerationError, match="ANALYSIS_VALIDATION_FAILED"):
        await generate_shadow_dynamics(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type="PARTNER",
            knowledge=load_knowledge_base(KNOWLEDGE_ROOT),
            shadow_rules=load_shadow_interaction_rules(KNOWLEDGE_ROOT),
            llm=_LabelCitingProvider(),
            knowledge_version="0.1.0",
        )


async def test_result_level_backstop_also_sees_unicode_lookalikes(
    profile_a, profile_b, monkeypatch
) -> None:
    monkeypatch.setattr(
        pipeline,
        "_recommended_micro_tasks",
        lambda _ctx: ("Aufgabe \uff3bprofile_fact\uff1aa:expression\uff3d.",),
    )
    with pytest.raises(AnalysisGenerationError, match="ANALYSIS_VALIDATION_FAILED"):
        await generate_shadow_dynamics(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type="PARTNER",
            knowledge=load_knowledge_base(KNOWLEDGE_ROOT),
            shadow_rules=load_shadow_interaction_rules(KNOWLEDGE_ROOT),
            llm=_LabelCitingProvider(),
            knowledge_version="0.1.0",
        )


async def test_prompt_forbids_labels_and_names_the_replacement(profile_a, profile_b) -> None:
    frame = load_relationship_frame(KNOWLEDGE_ROOT, "PARTNER")
    assert frame is not None
    llm = _LabelCitingProvider()
    result = await generate_relationship_analysis(
        profile_a=profile_a,
        profile_b=profile_b,
        relationship_type="PARTNER",
        frame_knowledge=frame,
        llm=llm,
        knowledge_version="0.1.0",
    )
    instructions = llm.requests[0].system_instructions
    assert "Never reproduce the bracketed context-block labels" in instructions
    assert "instead of the label" in instructions
    assert result.prompt_version == "numra-relationship-v3"


# --------------------------------------------------------------------------- Wissen


_KNOWLEDGE_TOKEN = re.compile(
    r"[{}]|\[\s*(?:profile_fact|knowledge|system|instruction_supplement|"
    r"untrusted_user_content|user_instructions)\b",
    re.IGNORECASE,
)


@pytest.mark.parametrize("subdir", ("relationship-frames", "shadow-interaction", "numbers"))
def test_curated_knowledge_that_feeds_analyses_carries_no_template_tokens(subdir) -> None:
    files = sorted((KNOWLEDGE_ROOT / subdir).rglob("*.yaml"))
    assert files
    for path in files:
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            assert not _KNOWLEDGE_TOKEN.search(line), f"{path}:{number}: {line[:100]!r}"
