"""Report manifests — canon-spec-adjacent, master-prompt §102/§105/§106.

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

#: (min_words, max_words) per master prompt §102. CUSTOM has no fixed range — the
#: caller supplies total_target_words directly.
REPORT_TYPE_WORD_RANGES: dict[str, tuple[int, int]] = {
    "QUICK": (1000, 2000),
    "FULL": (5000, 10000),
    "ULTIMATE": (15000, 30000),
}

#: (section_id, title, weight, metric_refs, knowledge_refs). Weight distributes the
#: manifest's total_target_words proportionally across sections. Scoped to the metrics
#: and knowledge actually available from Phase 3 (composer.CORE_METRIC_IDS plus the
#: special-number/cycle/timing groups); this is a judgment call, not a literal
#: transcription of master prompt §106's full (much longer) topic list — see
#: specs/evidence/phase-4.md.
_SECTION_DEFS: tuple[tuple[str, str, float, tuple[str, ...], tuple[str, ...]], ...] = (
    ("executive_profile", "Executive Profile", 1.4, ("life_path", "expression", "soul_urge"), ()),
    ("life_path", "Life Path", 1.2, ("life_path",), ("life_path",)),
    ("expression", "Expression / Destiny", 1.0, ("expression",), ("expression",)),
    ("soul_urge", "Soul Urge", 1.0, ("soul_urge",), ("soul_urge",)),
    ("personality", "Personality", 1.0, ("personality",), ("personality",)),
    ("birthday", "Birthday", 0.6, ("birthday",), ("birthday",)),
    ("attitude", "Attitude", 0.6, ("attitude",), ("attitude",)),
    ("maturity", "Maturity", 0.7, ("maturity",), ("maturity",)),
    ("balance", "Balance", 0.5, ("balance",), ("balance",)),
    (
        "special_numbers",
        "Hidden Passion, Karmic Lessons & Subconscious Self",
        1.1,
        (),
        ("hidden_passion", "karmic_lessons", "subconscious_self"),
    ),
    ("cycles", "Pinnacles & Challenges", 1.3, (), ("pinnacle", "challenge")),
    (
        "timing",
        "Personal Year, Month & Day",
        1.1,
        ("personal_year", "personal_month", "personal_day"),
        ("personal_year", "personal_month", "personal_day"),
    ),
    ("development", "Practical Development Plan", 1.0, (), ()),
    ("calculation_appendix", "Calculation Appendix", 0.7, (), ()),
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
    prompt_version: str = "numra-report-v1"


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
