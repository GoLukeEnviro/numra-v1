"""Composes a structured, German-language :class:`Interpretation` from a
`CanonicalProfile` (already computed by `numra_numerology`) plus the loaded
`KnowledgeBase`.

This module NEVER calculates a numerology value and NEVER invents a number that is
not already present on the `CanonicalProfile` — it only *reads* values the engine
already produced (``effective_value``, ``root_value``, ``master_number``,
``display_value``, flags) and resolves German text for them from `knowledge/`.
Composition is plain, explicit, rule-based string building (f-strings) — no template
engine, no LLM call.

Scope (judgment call — see the phase-3 evidence notes): "core metric" sections cover
the eight `CoreNumbers` fields that are themselves `CalculationMetric` instances with a
uniform `metric_id`/`display_value` shape: life_path, birthday, attitude, expression,
soul_urge, personality, maturity, balance. The remaining `core_numbers` entries
(hidden_passion, karmic_lessons, subconscious_self, cornerstone, capstone, first_vowel,
intensity_table) use structurally different schemas (multi-value sets, letters, a bare
count, a zero-filled table) rather than a single number + display_value, so composing a
uniform interpretation section for them is left to a later phase.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from numra_interpretation.knowledge_loader import KnowledgeBase
from numra_interpretation.knowledge_models import KarmicDebtKnowledge, NumberKnowledge
from numra_numerology.models.metric import CalculationMetric
from numra_numerology.models.profile import CanonicalProfile

__all__ = ["CORE_METRIC_IDS", "Interpretation", "InterpretationSection", "compose_interpretation"]

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


class Interpretation(BaseModel):
    """A full, structured, traceable interpretation for one `CanonicalProfile`."""

    model_config = ConfigDict(frozen=True)

    schema_version: str
    knowledge_version: str
    profile_deterministic_hash: str | None
    sections: tuple[InterpretationSection, ...]


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
    )
