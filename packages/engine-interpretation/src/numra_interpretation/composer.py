"""Composes a structured, German-language :class:`Interpretation` from a
`CanonicalProfile` (already computed by `numra_numerology`) plus the loaded
`KnowledgeBase`.

This module NEVER calculates a numerology value and NEVER invents a number that is
not already present on the `CanonicalProfile` — it only *reads* values the engine
already produced (``effective_value``, ``root_value``, ``master_number``,
``display_value``, flags) and resolves German text for them from `knowledge/`.
Composition is plain, explicit, rule-based string building (f-strings) — no template
engine, no LLM call.

Scope: "core metric" sections (`compose_section`, `Interpretation.sections`) cover the
eight `CoreNumbers` fields that are themselves `CalculationMetric` instances with a
uniform `metric_id`/`display_value` shape: life_path, birthday, attitude, expression,
soul_urge, personality, maturity, balance. `Timing.personal_year/month/day` share that
same shape and get their own `compose_timing_sections`/`Interpretation.timing_sections`
(kept separate since they describe a moment, not a stable trait).

The remaining `core_numbers`/`cycles` entries (hidden_passion, karmic_lessons,
subconscious_self, cornerstone, capstone, first_vowel, intensity_table, the four
Pinnacles, the four Challenges) use structurally different schemas (multi-value sets,
letters, a bare count, a frequency table, age windows) rather than a single number +
display_value — V1.5 Epic J composes each of these individually via
`compose_extended_sections`/`Interpretation.extended_sections`, still reading only
values already present on the profile plus text from `knowledge/`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from numra_interpretation.knowledge_loader import KnowledgeBase
from numra_interpretation.knowledge_models import KarmicDebtKnowledge, NumberKnowledge
from numra_numerology.models.cycles import PinnacleWindow
from numra_numerology.models.metric import (
    CalculationMetric,
    HiddenPassion,
    KarmicLessons,
    LetterResult,
    SubconsciousSelf,
)
from numra_numerology.models.profile import CanonicalProfile
from numra_numerology.models.reduction import ReductionResult

__all__ = [
    "CORE_METRIC_IDS",
    "TIMING_METRIC_IDS",
    "ExtendedInterpretationSection",
    "Interpretation",
    "InterpretationSection",
    "compose_extended_sections",
    "compose_interpretation",
]

#: The `CoreNumbers` fields that are `CalculationMetric` instances — see module
#: docstring for why the other `core_numbers` entries are out of scope here.
CORE_METRIC_IDS: tuple[str, ...] = (
    "life_path",
    "birthday",
    "attitude",
    "expression",
    "soul_urge",
    "personality",
    "maturity",
    "balance",
)

#: `Timing` fields — also `CalculationMetric` instances, so they reuse
#: `compose_section` directly (V1.5 Epic J).
TIMING_METRIC_IDS: tuple[str, ...] = ("personal_year", "personal_month", "personal_day")


class InterpretationSection(BaseModel):
    """One composed interpretation section for a single core metric."""

    model_config = ConfigDict(frozen=True)

    metric_id: str
    display_name_de: str
    display_value: str
    number_value: int
    is_master: bool
    core_themes: tuple[str, ...]
    shadows: tuple[str, ...]
    karmic_debt_compound: str | None
    text_de: str


class ExtendedInterpretationSection(BaseModel):
    """V1.5 Epic J: a composed section for a `core_numbers`/`cycles` entry whose
    schema isn't a uniform single-number `CalculationMetric` (multi-value sets,
    letters, a bare count, a frequency table). Same non-negotiables as
    `InterpretationSection`: every fact quoted here already exists on the profile or
    in `knowledge/`, nothing is computed or invented in this module."""

    model_config = ConfigDict(frozen=True)

    metric_id: str
    display_name_de: str
    text_de: str
    knowledge_refs: tuple[str, ...]


class Interpretation(BaseModel):
    """A full, structured, traceable interpretation for one `CanonicalProfile`."""

    model_config = ConfigDict(frozen=True)

    schema_version: str
    knowledge_version: str
    profile_deterministic_hash: str | None
    sections: tuple[InterpretationSection, ...]
    #: `Timing.personal_year/month/day` — same section shape as `sections`, kept
    #: separate since they describe a moment (as_of_date), not a stable trait.
    timing_sections: tuple[InterpretationSection, ...] = ()
    #: Hidden Passion, Karmic Lessons, Subconscious Self, Cornerstone, Capstone,
    #: First Vowel, Intensity Table, the four Pinnacles, the four Challenges.
    extended_sections: tuple[ExtendedInterpretationSection, ...] = ()


def _resolve_number_knowledge(
    metric: CalculationMetric, knowledge: KnowledgeBase
) -> NumberKnowledge:
    """The number whose knowledge applies to this metric: the master number if one was
    preserved (canon-spec.md §1/§2), otherwise the single-digit root."""
    resolved_value = (
        metric.effective_value if metric.master_number is not None else metric.root_value
    )
    return knowledge.number(resolved_value)


def _resolve_karmic_debt(
    metric: CalculationMetric, knowledge: KnowledgeBase
) -> KarmicDebtKnowledge | None:
    for flag in metric.flags:
        if flag.code == "KARMIC_DEBT" and flag.value is not None:
            return knowledge.karmic_debt(flag.value)
    return None


def _compose_text(
    *,
    metric: CalculationMetric,
    display_name_de: str,
    semantic_context_de: str,
    number_knowledge: NumberKnowledge,
    karmic: KarmicDebtKnowledge | None,
) -> str:
    themes = ", ".join(number_knowledge.core_themes)
    shadows = ", ".join(number_knowledge.shadows)
    sentences = [
        f"{display_name_de} ({metric.display_value}): {semantic_context_de}",
        f"Kernthemen der Zahl {number_knowledge.value}: {themes}.",
        f"Mögliche Schattenseiten: {shadows}.",
    ]
    if karmic is not None:
        karmic_themes = ", ".join(karmic.themes)
        sentences.append(
            f"Zusätzlich zeigt sich hier die karmische Zahl {karmic.compound} mit den "
            f"symbolischen Themen {karmic_themes}."
        )
    return " ".join(sentences)


def compose_section(
    metric_id: str, metric: CalculationMetric, knowledge: KnowledgeBase
) -> InterpretationSection:
    """Compose one section for a single core metric already present on the profile."""
    metric_knowledge = knowledge.metric(metric_id)
    number_knowledge = _resolve_number_knowledge(metric, knowledge)
    karmic = _resolve_karmic_debt(metric, knowledge)

    text_de = _compose_text(
        metric=metric,
        display_name_de=metric_knowledge.display_name_de,
        semantic_context_de=metric_knowledge.semantic_context_de,
        number_knowledge=number_knowledge,
        karmic=karmic,
    )

    return InterpretationSection(
        metric_id=metric_id,
        display_name_de=metric_knowledge.display_name_de,
        display_value=metric.display_value,
        number_value=number_knowledge.value,
        is_master=number_knowledge.is_master,
        core_themes=number_knowledge.core_themes,
        shadows=number_knowledge.shadows,
        karmic_debt_compound=karmic.compound if karmic is not None else None,
        text_de=text_de,
    )


def compose_timing_sections(
    profile: CanonicalProfile, knowledge: KnowledgeBase
) -> tuple[InterpretationSection, ...]:
    """Personal Year/Month/Day: `Timing` fields are `CalculationMetric` instances
    exactly like the core metrics, so `compose_section` applies unchanged."""
    return tuple(
        compose_section(metric_id, getattr(profile.timing, metric_id), knowledge)
        for metric_id in TIMING_METRIC_IDS
    )


def _themes_text(number_knowledge: NumberKnowledge) -> str:
    return ", ".join(number_knowledge.core_themes)


def _compose_hidden_passion(
    hidden_passion: HiddenPassion, knowledge: KnowledgeBase
) -> ExtendedInterpretationSection:
    metric_knowledge = knowledge.metric("hidden_passion")
    intro = f"{metric_knowledge.display_name_de}: {metric_knowledge.semantic_context_de}"
    if not hidden_passion.values:
        return ExtendedInterpretationSection(
            metric_id="hidden_passion",
            display_name_de=metric_knowledge.display_name_de,
            text_de=f"{intro} Für diesen Namen wurde kein eindeutig dominanter Wert ermittelt.",
            knowledge_refs=(),
        )
    entries = [(v, knowledge.number(v)) for v in hidden_passion.values]
    values_text = ", ".join(f"{v} ({_themes_text(nk)})" for v, nk in entries)
    text = f"{intro} Am häufigsten vertreten (jeweils {hidden_passion.frequency}x): {values_text}."
    refs = tuple(sorted({f"numbers/{v}" for v, _ in entries}))
    return ExtendedInterpretationSection(
        metric_id="hidden_passion",
        display_name_de=metric_knowledge.display_name_de,
        text_de=text,
        knowledge_refs=refs,
    )


def _compose_karmic_lessons(
    karmic_lessons: KarmicLessons, knowledge: KnowledgeBase
) -> ExtendedInterpretationSection:
    metric_knowledge = knowledge.metric("karmic_lessons")
    intro = f"{metric_knowledge.display_name_de}: {metric_knowledge.semantic_context_de}"
    if not karmic_lessons.values:
        return ExtendedInterpretationSection(
            metric_id="karmic_lessons",
            display_name_de=metric_knowledge.display_name_de,
            text_de=f"{intro} In diesem Namen fehlt kein Grundwert vollständig.",
            knowledge_refs=(),
        )
    entries = [(v, knowledge.number(v)) for v in karmic_lessons.values]
    values_text = ", ".join(f"{v} ({_themes_text(nk)})" for v, nk in entries)
    text = f"{intro} Fehlende Werte: {values_text}."
    refs = tuple(sorted({f"numbers/{v}" for v, _ in entries}))
    return ExtendedInterpretationSection(
        metric_id="karmic_lessons",
        display_name_de=metric_knowledge.display_name_de,
        text_de=text,
        knowledge_refs=refs,
    )


def _compose_subconscious_self(
    subconscious_self: SubconsciousSelf, knowledge: KnowledgeBase
) -> ExtendedInterpretationSection:
    metric_knowledge = knowledge.metric("subconscious_self")
    number_knowledge = knowledge.number(subconscious_self.value)
    text = (
        f"{metric_knowledge.display_name_de} ({subconscious_self.value}): "
        f"{metric_knowledge.semantic_context_de} "
        f"Kernthemen der Zahl {subconscious_self.value}: {_themes_text(number_knowledge)}."
    )
    return ExtendedInterpretationSection(
        metric_id="subconscious_self",
        display_name_de=metric_knowledge.display_name_de,
        text_de=text,
        knowledge_refs=(f"numbers/{subconscious_self.value}",),
    )


def _compose_letter_section(
    metric_id: str, letter_result: LetterResult, knowledge: KnowledgeBase
) -> ExtendedInterpretationSection:
    metric_knowledge = knowledge.metric(metric_id)
    intro = f"{metric_knowledge.display_name_de}: {metric_knowledge.semantic_context_de}"
    if letter_result.letter is None or letter_result.value is None:
        return ExtendedInterpretationSection(
            metric_id=metric_id,
            display_name_de=metric_knowledge.display_name_de,
            text_de=f"{intro} Für diesen Namen konnte kein Buchstabe ermittelt werden.",
            knowledge_refs=(),
        )
    number_knowledge = knowledge.number(letter_result.value)
    text = (
        f"{metric_knowledge.display_name_de} ({letter_result.letter}, Wert {letter_result.value}): "
        f"{metric_knowledge.semantic_context_de} "
        f"Kernthemen der Zahl {letter_result.value}: {_themes_text(number_knowledge)}."
    )
    return ExtendedInterpretationSection(
        metric_id=metric_id,
        display_name_de=metric_knowledge.display_name_de,
        text_de=text,
        knowledge_refs=(f"numbers/{letter_result.value}",),
    )


def _compose_intensity_table(
    intensity_table: dict[str, int], knowledge: KnowledgeBase
) -> ExtendedInterpretationSection:
    metric_knowledge = knowledge.metric("intensity_table")
    parts = [f"{metric_knowledge.display_name_de}: {metric_knowledge.semantic_context_de}"]
    refs: set[str] = set()
    if intensity_table:
        max_count = max(intensity_table.values())
        dominant = sorted(
            int(k) for k, v in intensity_table.items() if max_count > 0 and v == max_count
        )
        absent = sorted(int(k) for k, v in intensity_table.items() if v == 0)
        if dominant:
            entries = [(v, knowledge.number(v)) for v in dominant]
            text = ", ".join(f"{v} ({_themes_text(nk)})" for v, nk in entries)
            parts.append(f"Am stärksten vertreten (je {max_count}x): {text}.")
            refs.update(f"numbers/{v}" for v, _ in entries)
        if absent:
            entries = [(v, knowledge.number(v)) for v in absent]
            text = ", ".join(f"{v} ({_themes_text(nk)})" for v, nk in entries)
            parts.append(f"Nicht vertreten: {text}.")
            refs.update(f"numbers/{v}" for v, _ in entries)
    return ExtendedInterpretationSection(
        metric_id="intensity_table",
        display_name_de=metric_knowledge.display_name_de,
        text_de=" ".join(parts),
        knowledge_refs=tuple(sorted(refs)),
    )


def _compose_pinnacle(
    index: int, result: ReductionResult, window: PinnacleWindow, knowledge: KnowledgeBase
) -> ExtendedInterpretationSection:
    metric_knowledge = knowledge.metric("pinnacle")
    number_knowledge = knowledge.number(result.effective_value)
    age_text = (
        f"ab {window.start_age} Jahren"
        if window.end_age is None
        else f"von {window.start_age} bis {window.end_age} Jahren"
    )
    text = (
        f"{metric_knowledge.display_name_de} {index} ({result.display_value}, {age_text}): "
        f"{metric_knowledge.semantic_context_de} "
        f"Kernthemen der Zahl {result.effective_value}: {_themes_text(number_knowledge)}."
    )
    return ExtendedInterpretationSection(
        metric_id=f"pinnacle_{index}",
        display_name_de=f"{metric_knowledge.display_name_de} {index}",
        text_de=text,
        knowledge_refs=(f"numbers/{result.effective_value}",),
    )


def _compose_challenge(
    index: int, value: int, knowledge: KnowledgeBase
) -> ExtendedInterpretationSection:
    metric_knowledge = knowledge.metric("challenge")
    if value == 0:
        # Traditional Pythagorean reading: 0 means no fixed challenge number was
        # produced, not "no knowledge exists for 0" — there genuinely is no
        # `knowledge/numbers/0.yaml`, so this is composed directly rather than a
        # number lookup.
        text = (
            f"{metric_knowledge.display_name_de} {index} (0): "
            f"{metric_knowledge.semantic_context_de} "
            "Die 0 wird traditionell als Fehlen einer festen Herausforderungszahl gedeutet — "
            "symbolisch für Vielseitigkeit ohne einen einzelnen thematischen Schwerpunkt."
        )
        return ExtendedInterpretationSection(
            metric_id=f"challenge_{index}",
            display_name_de=f"{metric_knowledge.display_name_de} {index}",
            text_de=text,
            knowledge_refs=(),
        )
    number_knowledge = knowledge.number(value)
    text = (
        f"{metric_knowledge.display_name_de} {index} ({value}): "
        f"{metric_knowledge.semantic_context_de} "
        f"Kernthemen der Zahl {value}: {_themes_text(number_knowledge)}."
    )
    return ExtendedInterpretationSection(
        metric_id=f"challenge_{index}",
        display_name_de=f"{metric_knowledge.display_name_de} {index}",
        text_de=text,
        knowledge_refs=(f"numbers/{value}",),
    )


def compose_extended_sections(
    profile: CanonicalProfile, knowledge: KnowledgeBase
) -> tuple[ExtendedInterpretationSection, ...]:
    """Compose sections for every `core_numbers`/`cycles` entry not covered by
    `compose_section` (see module docstring and `ExtendedInterpretationSection`)."""
    core = profile.core_numbers
    cycles = profile.cycles
    sections = [
        _compose_hidden_passion(core.hidden_passion, knowledge),
        _compose_karmic_lessons(core.karmic_lessons, knowledge),
        _compose_subconscious_self(core.subconscious_self, knowledge),
        _compose_letter_section("cornerstone", core.cornerstone, knowledge),
        _compose_letter_section("capstone", core.capstone, knowledge),
        _compose_letter_section("first_vowel", core.first_vowel, knowledge),
        _compose_intensity_table(core.intensity_table, knowledge),
    ]
    pinnacle_results = (
        cycles.pinnacles.pinnacle_1,
        cycles.pinnacles.pinnacle_2,
        cycles.pinnacles.pinnacle_3,
        cycles.pinnacles.pinnacle_4,
    )
    for index, (result, window) in enumerate(
        zip(pinnacle_results, cycles.pinnacles.windows, strict=True), start=1
    ):
        sections.append(_compose_pinnacle(index, result, window, knowledge))
    challenge_values = (
        cycles.challenges.challenge_1,
        cycles.challenges.challenge_2,
        cycles.challenges.challenge_3,
        cycles.challenges.challenge_4,
    )
    for index, value in enumerate(challenge_values, start=1):
        sections.append(_compose_challenge(index, value, knowledge))
    return tuple(sections)


def compose_interpretation(profile: CanonicalProfile, knowledge: KnowledgeBase) -> Interpretation:
    """Compose the full structured interpretation for a `CanonicalProfile`.

    Reads every value from ``profile`` — it never recomputes or overrides anything the
    numerology engine already produced.
    """
    sections = tuple(
        compose_section(metric_id, getattr(profile.core_numbers, metric_id), knowledge)
        for metric_id in CORE_METRIC_IDS
    )
    return Interpretation(
        schema_version="1.0.0",
        knowledge_version=knowledge.manifest.version,
        profile_deterministic_hash=profile.deterministic_hash,
        sections=sections,
        timing_sections=compose_timing_sections(profile, knowledge),
        extended_sections=compose_extended_sections(profile, knowledge),
    )
