"""Report manifests — section list, German titles, prompt version.

A `ReportManifest` is pure data: report type, target word counts per section, and the
metric/knowledge refs each section is grounded in. Building one performs no LLM calls
and no calculation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

__all__ = [
    "REPORT_TYPE_WORD_RANGES",
    "ReportManifest",
    "ReportSectionSpec",
    "ReportType",
    "build_manifest",
]

ReportType = Literal["QUICK", "FULL", "ULTIMATE", "CUSTOM"]

REPORT_TYPE_WORD_RANGES: dict[str, tuple[int, int]] = {
    "QUICK": (1000, 2000),
    "FULL": (5000, 10000),
    "ULTIMATE": (15000, 30000),
}

#: German titles for language=de reports. Weight distributes total_target_words.
_SECTION_DEFS: tuple[tuple[str, str, float, tuple[str, ...], tuple[str, ...]], ...] = (
    ("executive_profile", "Profilüberblick", 1.4, ("life_path", "expression", "soul_urge"), ()),
    ("life_path", "Lebenszahl", 1.2, ("life_path",), ("life_path",)),
    ("expression", "Ausdruckszahl", 1.0, ("expression",), ("expression",)),
    ("soul_urge", "Seelenzahl", 1.0, ("soul_urge",), ("soul_urge",)),
    ("personality", "Persönlichkeitszahl", 1.0, ("personality",), ("personality",)),
    ("birthday", "Geburtstagszahl", 0.6, ("birthday",), ("birthday",)),
    ("attitude", "Einstellungszahl", 0.6, ("attitude",), ("attitude",)),
    ("maturity", "Reifezahl", 0.7, ("maturity",), ("maturity",)),
    ("balance", "Balancezahl", 0.5, ("balance",), ("balance",)),
    (
        "special_numbers",
        "Verborgene Leidenschaft, karmische Lektionen und Unterbewusstsein",
        1.1,
        (),
        ("hidden_passion", "karmic_lessons", "subconscious_self"),
    ),
    ("cycles", "Höhepunkte und Herausforderungen", 1.3, (), ("pinnacle", "challenge")),
    (
        "timing",
        "Persönliches Jahr, Monat und Tag",
        1.1,
        ("personal_year", "personal_month", "personal_day"),
        ("personal_year", "personal_month", "personal_day"),
    ),
    ("development", "Praktischer Entwicklungsplan", 1.0, (), ()),
    ("calculation_appendix", "Rechenanhang", 0.7, (), ()),
)


class ReportSectionSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    section_id: str
    title: str
    order_index: int
    target_word_count: int
    metric_refs: tuple[str, ...]
    knowledge_refs: tuple[str, ...]


class ReportManifest(BaseModel):
    model_config = ConfigDict(frozen=True)

    report_type: ReportType
    language: str
    calculation_id: str
    total_target_words: int
    sections: tuple[ReportSectionSpec, ...]
    prompt_version: str = "numra-report-v3"


def build_manifest(
    *,
    report_type: ReportType,
    calculation_id: str,
    language: str = "de",
    custom_total_target_words: int | None = None,
) -> ReportManifest:
    if report_type == "CUSTOM":
        if custom_total_target_words is None:
            raise ValueError("custom_total_target_words is required when report_type='CUSTOM'")
        total_target_words = custom_total_target_words
    else:
        low, high = REPORT_TYPE_WORD_RANGES[report_type]
        total_target_words = (low + high) // 2

    total_weight = sum(weight for _, _, weight, _, _ in _SECTION_DEFS)
    sections = tuple(
        ReportSectionSpec(
            section_id=section_id,
            title=title,
            order_index=index,
            target_word_count=max(1, round(total_target_words * weight / total_weight)),
            metric_refs=metric_refs,
            knowledge_refs=knowledge_refs,
        )
        for index, (section_id, title, weight, metric_refs, knowledge_refs) in enumerate(
            _SECTION_DEFS
        )
    )

    return ReportManifest(
        report_type=report_type,
        language=language,
        calculation_id=calculation_id,
        total_target_words=total_target_words,
        sections=sections,
    )
