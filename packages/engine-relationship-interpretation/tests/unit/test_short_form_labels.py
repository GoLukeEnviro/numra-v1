"""Regression: das verkuerzte Block-Label ``[a:life_path]`` wird eindeutig aufgeloest oder
fail-closed abgelehnt -- nie als fertiger Text gespeichert.

Anlass (Audit-Abnahme 2026-10-09): 4 von 6 neu erzeugten Beziehungsanalysen (Prompt v2 und
v3, Status COMPLETE) enthielten ``[a:life_path]``, ``[b:expression]``, ``[a:soul_urge]`` ...
im Satz. Ursache: die Systemanweisung verwies auf "die Platzhalter-Syntax, die du bekommen
hast" -- sie wurde aber nirgends genannt --, das Modell kuerzte das einzige geklammerte
Muster, das es kannte (``[profile_fact:a:life_path]``), auf ``[a:life_path]``. Der Repair aus
#292 kannte nur die lange Form, und der Leftover-Check erkannte die kurze nicht.
Die Beispielsaetze sind neu formuliert; nur die Token-Formen stammen aus dem Audit.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from numra_interpretation.llm.types import (
    ContextBlock,
    GenerationRequest,
    GenerationResult,
    ProviderHealth,
    StructuredGenerationRequest,
)
from numra_interpretation.llm.validator import (
    build_metric_display_value_index,
    build_special_claim_index,
)
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput
from numra_relationship_interpretation import pipeline
from numra_relationship_interpretation.errors import AnalysisGenerationError, InvalidAnalysisSection
from numra_relationship_interpretation.knowledge_loader import (
    load_relationship_frame,
    load_shadow_interaction_rules,
)
from numra_relationship_interpretation.pipeline import (
    PROMPT_VERSION,
    _repair_short_form_labels,
    _validate_and_resolve_text,
    generate_relationship_analysis,
    generate_shadow_dynamics,
)

pytestmark = pytest.mark.unit

KNOWLEDGE_ROOT = Path(__file__).resolve().parents[4] / "knowledge"

_AUDIT_METRIC_IDS = (
    "life_path",
    "expression",
    "soul_urge",
    "attitude",
    "balance",
    "subconscious_self",
    "personal_year",
    "challenge_1",
    "challenge_2",
)


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


# --------------------------------------------------------------------------- Repair


@pytest.mark.parametrize("role", ["a", "b"])
@pytest.mark.parametrize("metric_id", _AUDIT_METRIC_IDS)
def test_unique_short_label_becomes_the_sanctioned_placeholder(role, metric_id, blocks_ab) -> None:
    assert f"{role}:{metric_id}" in {b.label for b in blocks_ab}, "Audit-ID fehlt im Prompt"

    repaired = _repair_short_form_labels(
        f"Es zeigt sich durch [{role}:{metric_id}] ein Bild.", blocks_ab
    )

    assert repaired == f"Es zeigt sich durch {{{{metric:{role}:{metric_id}}}}} ein Bild."


@pytest.mark.parametrize(
    ("written", "expected_label"),
    (
        ("[A:life_path]", "a:life_path"),
        ("[a: life_path]", "a:life_path"),
        ("[ b : Soul_Urge ]", "b:soul_urge"),
        ("[B:EXPRESSION]", "b:expression"),
    ),
)
def test_case_and_blank_variants_of_a_known_label_are_repaired(
    written, expected_label, blocks_ab
) -> None:
    repaired = _repair_short_form_labels(f"Vor {written} nach.", blocks_ab)

    assert repaired == f"Vor {{{{metric:{expected_label}}}}} nach."


def test_every_occurrence_in_a_sentence_is_repaired(blocks_ab) -> None:
    repaired = _repair_short_form_labels(
        "Zwischen [a:life_path] und [b:life_path] zeigt sich, dass [a:expression] offen wirkt.",
        blocks_ab,
    )

    assert repaired == (
        "Zwischen {{metric:a:life_path}} und {{metric:b:life_path}} zeigt sich, "
        "dass {{metric:a:expression}} offen wirkt."
    )


def test_repair_resolves_to_the_canonical_value_never_to_model_text(
    profile_a, profile_b, blocks_ab
) -> None:
    text = "Person A bringt durch [a:life_path] Weite ein, Person B durch [b:expression] Ruhe."

    resolved = _validate_and_resolve_text(
        _repair_short_form_labels(text, blocks_ab),
        profile_a=profile_a,
        profile_b=profile_b,
        is_mock_provider=False,
    )

    life_path_a = build_metric_display_value_index(profile_a)["life_path"]
    expression_b = build_metric_display_value_index(profile_b)["expression"]
    assert (
        resolved
        == f"Person A bringt durch {life_path_a} Weite ein, Person B durch {expression_b} Ruhe."
    )


def test_a_label_of_a_fact_this_request_did_not_carry_is_not_repaired(blocks_a_only) -> None:
    text = "Das zeigt [b:life_path] im Satz."

    assert _repair_short_form_labels(text, blocks_a_only) == text


def test_an_unknown_metric_id_is_not_repaired(blocks_ab) -> None:
    text = "Das zeigt [a:does_not_exist] im Satz."

    assert _repair_short_form_labels(text, blocks_ab) == text


def test_a_special_id_is_not_repaired(profile_a, blocks_ab) -> None:
    special_id = next(iter(build_special_claim_index(profile_a)))
    text = f"Das zeigt [a:{special_id}] im Satz."

    assert _repair_short_form_labels(text, blocks_ab) == text


@pytest.mark.parametrize(
    "text",
    (
        "Das zeigt [[a:life_path]] im Satz.",
        "Das zeigt [a:[a:life_path]] im Satz.",
        "Das zeigt [a:life_path = 5] im Satz.",
        "Das zeigt [a:life_path:extra] im Satz.",
        "Das zeigt [a:life_path im Satz.",
        "Das zeigt a:life_path] im Satz.",
    ),
)
def test_nested_or_decorated_forms_are_not_repaired(text, blocks_ab) -> None:
    assert _repair_short_form_labels(text, blocks_ab) == text


@pytest.mark.parametrize(
    "text",
    (
        "Satz [а:life_path] mit kyrillischem a.",
        "Satz ［ａ：life_path］ voll breit.",
        "Satz [a​:life_path] mit Zero-Width.",
        "Satz [a:life​_path] mit Zero-Width in der ID.",
        "Satz [a:lіfe_path] mit kyrillischem i.",
    ),
)
def test_lookalike_labels_are_never_repaired(text, blocks_ab) -> None:
    assert _repair_short_form_labels(text, blocks_ab) == text


def test_only_profile_fact_blocks_make_a_label_known() -> None:
    blocks = (
        ContextBlock(role="knowledge", label="a:life_path", content="Wissen."),
        ContextBlock(role="instruction_supplement", label="b:expression", content="Anweisung."),
    )
    text = "Satz [a:life_path] und [b:expression]."

    assert _repair_short_form_labels(text, blocks) == text


@pytest.mark.parametrize(
    "text",
    (
        "Treffen um [10:30] Uhr.",
        "Siehe Buch [1].",
        "Ein Verhältnis a:b im Fliesstext.",
        "Variante [a] oder [b].",
        "Zitat „… [sic] …“ bleibt.",
    ),
)
def test_ordinary_text_is_untouched_by_the_repair(text, blocks_ab) -> None:
    assert _repair_short_form_labels(text, blocks_ab) == text


# --------------------------------------------------------------------------- Gate


@pytest.mark.parametrize("is_mock_provider", [False, True])
@pytest.mark.parametrize(
    "text",
    (
        "Im Gespräch bringt Person A durch [a:life_path] eine offene Perspektive ein.",
        "Das zeigt [a:does_not_exist] im Satz.",
        "Das zeigt [a:life_pa",
        "Das zeigt [b:soul_urge",
        "Satz endet mit [a:",
        "Das zeigt [[a:life_path]] im Satz.",
        "Das zeigt ［a：life_path］ im Satz.",
        "Das zeigt {{metric:a:life_pa",
        "Das zeigt {{metric:life_path}} ohne Rolle.",
        "Das zeigt life_path}} ohne Anfang.",
    ),
)
def test_unrepaired_remnants_are_rejected_by_the_validation_gate(
    text, is_mock_provider, profile_a, profile_b
) -> None:
    with pytest.raises(InvalidAnalysisSection):
        _validate_and_resolve_text(
            text, profile_a=profile_a, profile_b=profile_b, is_mock_provider=is_mock_provider
        )


@pytest.mark.parametrize(
    "text",
    (
        "Im Gespräch bringt Person A durch [a:life_path] eine offene Perspektive ein.",
        "Im freundschaftlichen Austausch wirkt [a:expression] offen und [b:expression] ruhig.",
        "Das zeigt [a:life_pa",
        "Das zeigt {{metric:a:life_pa",
    ),
)
def test_the_final_backstop_rejects_the_remnants_too(text) -> None:
    with pytest.raises(AnalysisGenerationError, match="ANALYSIS_VALIDATION_FAILED"):
        pipeline._assert_no_unresolved_tokens(["Sauberer Satz.", text])


@pytest.mark.parametrize(
    "text",
    (
        "Treffen um [10:30] Uhr, danach eine Pause für beide.",
        "Siehe Buch [1] und Fussnote [12] zur Nähe.",
        "Ein Verhältnis a:b im Fliesstext, nicht mehr.",
        "Aufzählung: a) Nähe, b) Freiraum, c) Vertrauen.",
        "Das Zitat „… [sic] …“ bleibt unverändert.",
        "Klammern (wie hier) und [Anmerkung der Redaktion] sind normale Prosa.",
    ),
)
def test_ordinary_german_text_with_brackets_and_colons_is_accepted(
    text, profile_a, profile_b
) -> None:
    resolved = _validate_and_resolve_text(
        text, profile_a=profile_a, profile_b=profile_b, is_mock_provider=True
    )
    assert resolved == text
    pipeline._assert_no_unresolved_tokens([text])


# --------------------------------------------------------------------------- Pipeline


class _TextProvider:
    """A real (non-mock) provider whose answer is ``text_for(first profile_fact label)``."""

    def __init__(self, text_for) -> None:
        self.text_for = text_for
        self.requests: list[StructuredGenerationRequest] = []
        self.labels: list[str] = []

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="healthy", provider="ollama_cloud", checked_at=dt.datetime.now(dt.UTC)
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        raise AssertionError("not used")

    async def generate_structured(self, request: StructuredGenerationRequest, schema: type):  # type: ignore[no-untyped-def]
        self.requests.append(request)
        label = next(b.label for b in request.context_blocks if b.role == "profile_fact")
        self.labels.append(label)
        return schema(text=self.text_for(label))


def _texts(result) -> list[str]:
    if hasattr(result, "dimensions"):
        return [s.text for d in result.dimensions for s in d.statements]
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


async def _run(kind, profile_a, profile_b, llm):
    if kind == "relationship":
        frame = load_relationship_frame(KNOWLEDGE_ROOT, "PARTNER")
        assert frame is not None
        return await generate_relationship_analysis(
            profile_a=profile_a,
            profile_b=profile_b,
            relationship_type="PARTNER",
            frame_knowledge=frame,
            llm=llm,
            knowledge_version="0.1.0",
        )
    from numra_interpretation.knowledge_loader import load_knowledge_base

    return await generate_shadow_dynamics(
        profile_a=profile_a,
        profile_b=profile_b,
        relationship_type="PARTNER",
        knowledge=load_knowledge_base(KNOWLEDGE_ROOT),
        shadow_rules=load_shadow_interaction_rules(KNOWLEDGE_ROOT),
        llm=llm,
        knowledge_version="0.1.0",
    )


@pytest.mark.parametrize("kind", ["relationship", "shadow"])
async def test_a_model_writing_the_short_label_gets_the_canonical_value(
    kind, profile_a, profile_b
) -> None:
    llm = _TextProvider(lambda label: f"Das ist gepraegt durch [{label}] im Alltag.")

    result = await _run(kind, profile_a, profile_b, llm)

    texts = _texts(result)
    assert len(texts) == len(llm.labels) > 0
    for text, label in zip(texts, llm.labels, strict=True):
        prefix, metric_id = label.split(":")
        profile = profile_a if prefix == "a" else profile_b
        expected = build_metric_display_value_index(profile)[metric_id]
        assert text == f"Das ist gepraegt durch {expected} im Alltag."


@pytest.mark.parametrize("kind", ["relationship", "shadow"])
@pytest.mark.parametrize(
    "template",
    (
        "Das ist gepraegt durch [a:does_not_exist] im Alltag.",
        "Das ist gepraegt durch [{label}] und [a:unbekannte_metrik] im Alltag.",
        "Das ist gepraegt durch [[{label}]] im Alltag.",
        "Das ist gepraegt durch [{label}",
        "Das ist gepraegt durch {{{{metric:{label}",
    ),
)
async def test_a_result_with_a_remnant_is_never_produced(
    kind, template, profile_a, profile_b
) -> None:
    llm = _TextProvider(lambda label: template.format(label=label))

    with pytest.raises(AnalysisGenerationError, match="ANALYSIS_VALIDATION_FAILED"):
        await _run(kind, profile_a, profile_b, llm)

    assert len(llm.requests) == 2, "genau ein Reparaturversuch, dann fail-closed"


@pytest.mark.parametrize("kind", ["relationship", "shadow"])
async def test_the_prompt_states_the_placeholder_syntax_literally(
    kind, profile_a, profile_b
) -> None:
    llm = _TextProvider(lambda label: "Saubere Prosa ohne Verweise.")

    await _run(kind, profile_a, profile_b, llm)

    instructions = llm.requests[0].system_instructions
    assert "{{metric:a:life_path}}" in instructions
    assert "{{metric:b:expression}}" in instructions
    assert "Square brackets never appear in your answer" in instructions
    assert "the metric-placeholder syntax you were given" not in instructions
    ids_block = next(
        b for b in llm.requests[0].context_blocks if b.label == "valid_placeholder_ids"
    )
    assert "{{metric:a:life_path}}" in ids_block.content


def test_prompt_version_marks_the_changed_instructions() -> None:
    assert PROMPT_VERSION == "numra-relationship-v4"


# --------------------------------------------------------------------------- echte Audit-Saetze


@pytest.mark.parametrize(
    "sentence",
    (
        "Im Austausch wirkt [a:expression] offen und idealistisch, Person B bleibt ruhiger.",
        "Person A bringt durch [a:life_path] eine nachdenkliche, abwägende Art ein.",
        "Die Nähe entsteht zwischen [a:life_path] und [b:life_path] im Alltag.",
        "Bedürfnisse: [b:soul_urge] sucht Tiefe, [a:soul_urge] eher Weite.",
        "Haltung [a:attitude], Balance [b:balance], Unterbewusstsein [a:subconscious_self].",
        "Persönliches Jahr [a:personal_year], Herausforderung [b:challenge_2], [a:challenge_1].",
    ),
)
def test_audit_sentences_resolve_to_canonical_values(
    sentence, profile_a, profile_b, blocks_ab
) -> None:
    resolved = _validate_and_resolve_text(
        _repair_short_form_labels(sentence, blocks_ab),
        profile_a=profile_a,
        profile_b=profile_b,
        is_mock_provider=True,
    )

    assert "[" not in resolved and "{" not in resolved
    index_a = build_metric_display_value_index(profile_a)
    index_b = build_metric_display_value_index(profile_b)
    expected = sentence
    for role, index in (("a", index_a), ("b", index_b)):
        for metric_id, value in index.items():
            expected = expected.replace(f"[{role}:{metric_id}]", value)
    assert resolved == expected


def test_a_special_fact_with_a_profile_fact_block_fails_closed_in_the_resolver(
    profile_a, profile_b, blocks_ab
) -> None:
    special_id = next(iter(build_special_claim_index(profile_a)))
    blocks = (
        *blocks_ab,
        ContextBlock(role="profile_fact", label=f"a:{special_id}", content="x"),
    )
    repaired = _repair_short_form_labels(f"Es zeigt [a:{special_id}] im Satz.", blocks)
    assert repaired == f"Es zeigt {{{{metric:a:{special_id}}}}} im Satz."

    with pytest.raises(InvalidAnalysisSection):
        _validate_and_resolve_text(
            repaired, profile_a=profile_a, profile_b=profile_b, is_mock_provider=False
        )


@pytest.mark.parametrize(
    "text",
    (
        "[A: Ich bin müde] sagte sie.",
        "Er sagte [a: Nähe] und ging.",
        "Siehe [Text](https://example.org) und Aufgabe [x].",
        "Mengenangabe a{1,2} im Beispiel.",
    ),
)
def test_analyses_accept_dialogue_but_keep_the_strict_brace_rule(
    text, profile_a, profile_b
) -> None:
    if "{" in text:
        with pytest.raises(InvalidAnalysisSection):
            _validate_and_resolve_text(
                text, profile_a=profile_a, profile_b=profile_b, is_mock_provider=True
            )
    else:
        assert (
            _validate_and_resolve_text(
                text, profile_a=profile_a, profile_b=profile_b, is_mock_provider=True
            )
            == text
        )


@pytest.mark.parametrize(
    "text",
    (
        "Es zeigt [a:life_path und geht weiter.",
        "Es zeigt [a:life_path, danach mehr.",
        "Es zeigt [a:life_path. Danach mehr.",
        "Es zeigt [b:expression) so.",
    ),
)
@pytest.mark.parametrize("is_mock_provider", [False, True])
def test_an_unclosed_known_label_mid_sentence_is_rejected_by_the_gate(
    text, is_mock_provider, profile_a, profile_b
) -> None:
    with pytest.raises(InvalidAnalysisSection):
        _validate_and_resolve_text(
            text, profile_a=profile_a, profile_b=profile_b, is_mock_provider=is_mock_provider
        )
    with pytest.raises(AnalysisGenerationError):
        pipeline._assert_no_unresolved_tokens([text])
