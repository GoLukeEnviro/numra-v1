"""Haertung der Gates in Analyse, Schatten-Dynamik und Copilot (Restluecken-Audit nach #308).

* Die neu erkannten Token-Formen (Look-alikes im Bezeichner, Fuell-/Steuerzeichen im Marker,
  ``str.format``-Felder, ``[a:foo]`` in Analysen) fuehren in jeder Pipeline zu einem
  abgelehnten Ergebnis -- nie zu einem gespeicherten.
* Das letzte Gate prueft das komplette Ergebnis, nicht nur die Aussagetexte.
* Was durchgeht, geht unveraendert durch: kein Gate normalisiert den gespeicherten Text.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from pydantic import BaseModel

from numra_interpretation.knowledge_loader import load_knowledge_base
from numra_interpretation.llm.rendering_guard import MAX_CHECKED_TEXT_CHARS
from numra_interpretation.llm.types import (
    ContextBlock,
    ProviderHealth,
    StructuredGenerationRequest,
)
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput
from numra_relationship_interpretation import pipeline
from numra_relationship_interpretation.copilot_pipeline import generate_copilot_reply
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


class _ScriptedProvider:
    """Ein echter (nicht-Mock) Provider, der immer denselben Text zurueckgibt."""

    def __init__(self, text: str, *, reply_schema: bool = False) -> None:
        self._text = text
        self._reply_schema = reply_schema
        self.calls = 0

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="healthy", provider="scripted", checked_at=dt.datetime.now(dt.UTC)
        )

    async def generate(self, request):  # pragma: no cover - nicht benutzt
        raise NotImplementedError

    async def generate_structured(
        self, request: StructuredGenerationRequest, schema: type[BaseModel]
    ) -> BaseModel:
        self.calls += 1
        payload: dict[str, object] = {"text": self._text}
        if self._reply_schema:
            payload["basis_type"] = "NUMEROLOGY_MODEL"
        return schema.model_validate(payload)


async def _analysis(kind: str, text: str, profile_a, profile_b):
    llm = _ScriptedProvider(text)
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
    return await generate_shadow_dynamics(
        profile_a=profile_a,
        profile_b=profile_b,
        relationship_type="PARTNER",
        knowledge=load_knowledge_base(KNOWLEDGE_ROOT),
        shadow_rules=load_shadow_interaction_rules(KNOWLEDGE_ROOT),
        llm=llm,
        knowledge_version="0.1.0",
    )


def _all_statement_texts(kind: str, result) -> list[str]:
    if kind == "relationship":
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


# --------------------------------------------------------------------------- Analysen

_NEW_FORMS = (
    "Ein Satz mit [a:does_not_exist_ɡ] im Text.",  # Look-alike ɡ im Bezeichner
    "Ein Satz mit [a:does_not_exist_һ] im Text.",  # Cyrillic һ
    "Ein Satz mit [profile_faᴄt:a:expression] im Text.",  # Kapitaelchen-c im Marker
    "Ein Satz mit [profㅤile_fact:a:expression] im Text.",  # Hangul-Filler im Marker
    "Ein Satz mit [prof⠀ile_fact:a:expression] im Text.",  # Braille-Blank
    "Ein Satz mit [prof\x07ile_fact:a:expression] im Text.",  # Steuerzeichen
    "Ein Satz mit [prof‮ile_fact:a:expression] im Text.",  # BiDi-Override
    "Ein Satz mit [a:life_path] im Text.",  # Private Use im Bezeichner
    "Ein Satz mit [a:foo] im Text.",  # unbekannte ID ohne Unterstrich (streng)
    "Ein Satz mit {0} im Text.",
    "Ein Satz mit {name!r} im Text.",
    "Ein Satz mit {:>10} im Text.",
    "Ein Satz mit ❴❴metric:a:life_path❵❵ im Text.",
)


@pytest.mark.parametrize("kind", ["relationship", "shadow"])
@pytest.mark.parametrize("text", _NEW_FORMS)
async def test_new_token_forms_fail_closed_in_every_analysis(kind, text, profile_a, profile_b):
    with pytest.raises(AnalysisGenerationError):
        await _analysis(kind, text, profile_a, profile_b)


_CLEAN_BUT_UNUSUAL = (
    "Ayşe sagt: ısı und İzmir sind wörtlich gemeint, Straße, Größe und Maß auch.",
    "Zwischen Nähe \U0001f468‍\U0001f469‍\U0001f467 und Freiraum­ liegt Wort​Trenner.",
    "Он сказал «да», και ο Σωκράτης απάντησε: 日本語も大丈夫です。",
    "Ein Satz mit [Anmerkung der Redaktion] und (Klammern) und a:b als Verhältnis.",
    "Er sagte [A: Ich bin müde] und ging.",
)


@pytest.mark.parametrize("kind", ["relationship", "shadow"])
@pytest.mark.parametrize("text", _CLEAN_BUT_UNUSUAL)
async def test_clean_text_is_stored_exactly_as_the_provider_wrote_it(
    kind, text, profile_a, profile_b
):
    result = await _analysis(kind, text, profile_a, profile_b)

    texts = _all_statement_texts(kind, result)
    assert texts
    assert all(stored == text for stored in texts)


async def test_an_oversize_statement_is_rejected_not_stored(profile_a, profile_b):
    with pytest.raises(AnalysisGenerationError):
        await _analysis("relationship", "Satz. " * MAX_CHECKED_TEXT_CHARS, profile_a, profile_b)


def test_final_gate_walks_the_complete_result_not_only_the_statement_texts() -> None:
    clean = {
        "dimensions": [{"statements": [{"text": "Sauber.", "canonical_refs": ["metric:a:x"]}]}]
    }
    pipeline._assert_no_unresolved_tokens(clean)

    for field in ("canonical_refs", "knowledge_refs", "workspace_evidence_refs"):
        dirty = {"dimensions": [{"statements": [{"text": "Sauber.", field: ["[a:foo]"]}]}]}
        with pytest.raises(AnalysisGenerationError, match="ANALYSIS_VALIDATION_FAILED"):
            pipeline._assert_no_unresolved_tokens(dirty)


def test_final_gate_message_names_the_token_but_never_the_prose() -> None:
    secret = "Vertraulicher Satz ueber Anna Berger"
    with pytest.raises(AnalysisGenerationError) as excinfo:
        pipeline._assert_no_unresolved_tokens([f"{secret} {{0}} geht weiter"])

    assert "unresolved token" in str(excinfo.value)
    assert "Anna" not in str(excinfo.value) and "Vertraulich" not in str(excinfo.value)


# --------------------------------------------------------------------------- Copilot


def _copilot_request() -> StructuredGenerationRequest:
    return StructuredGenerationRequest(
        system_instructions="sys",
        context_blocks=(ContextBlock(role="profile_fact", label="p", content="life_path=6"),),
        user_instructions="Was sagt mein Lebenspfad aus?",
        target_schema_name="CopilotGeneratedReply",
    )


async def _copilot(text: str):
    profile = calculate_profile(
        PersonInput(
            birth_first_names="Anna",
            birth_middle_names=None,
            birth_last_name="Berger",
            birth_date=dt.date(1990, 3, 14),
        ),
        as_of_date=dt.date(2026, 8, 19),
    )
    llm = _ScriptedProvider(text, reply_schema=True)
    result = await generate_copilot_reply(
        request=_copilot_request(),
        llm=llm,
        knowledge_version="0.1.0",
        grounding_profiles=(profile,),
    )
    return result, llm


@pytest.mark.parametrize(
    "text",
    (
        "Dein Lebenspfad ist {0} und traegt dich.",
        "Dein Lebenspfad ist {name!r} und traegt dich.",
        "Dein Lebenspfad ist {:>10} und traegt dich.",
        "Dein Lebenspfad ist {0.attr} und traegt dich.",
        "Dein Lebenspfad wird durch [profㅤile_fact:requester] beschrieben.",
        "Dein Lebenspfad wird durch [profile_faᴄt:requester] beschrieben.",
        "Dein Lebenspfad wird durch [a:life_path_ɡ] beschrieben.",
        "Dein Lebenspfad wird durch [a:life_pa\x1bth] beschrieben.",
        "Dein Lebenspfad wird durch [b:life_path‍] beschrieben.",
        "Dein Lebenspfad wird durch [a:pinnacle_١] beschrieben.",
    ),
)
async def test_copilot_rejects_the_new_token_forms_after_one_repair(text) -> None:
    with pytest.raises(AnalysisGenerationError):
        await _copilot(text)


async def test_copilot_rejects_an_oversize_reply() -> None:
    with pytest.raises(AnalysisGenerationError):
        await _copilot("Antwort. " * MAX_CHECKED_TEXT_CHARS)


@pytest.mark.parametrize("text", _CLEAN_BUT_UNUSUAL)
async def test_copilot_reply_text_is_returned_unchanged(text) -> None:
    result, llm = await _copilot(text)

    assert result.text == text
    assert llm.calls == 1


@pytest.mark.parametrize(
    "text",
    (
        "Die Menge {1, 2, 3} und a{1,2} sowie x^{2} bleiben Prosa.",
        'Ein JSON-Beispiel {"name": "Anna"} und Code { return; } bleiben Prosa.',
        "Ein unbekanntes [a:foo] ohne Unterstrich bleibt im Copilot Prosa.",
    ),
)
async def test_copilot_keeps_the_lenient_mode_for_braces_and_unknown_compact_labels(text) -> None:
    result, _llm = await _copilot(text)

    assert result.text == text
