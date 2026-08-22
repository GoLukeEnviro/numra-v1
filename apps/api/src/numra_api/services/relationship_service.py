from __future__ import annotations

from pathlib import Path
from typing import Any

from numra_interpretation.knowledge_loader import load_knowledge_base

#: canon-spec §59 — the exact metric pairs V1 is allowed to compare. No invented
#: compatibility percentage is computed anywhere in this module.
_COMPARED_METRICS: tuple[tuple[str, str], ...] = (
    ("core_numbers", "life_path"),
    ("core_numbers", "expression"),
    ("core_numbers", "soul_urge"),
    ("core_numbers", "personality"),
    ("core_numbers", "maturity"),
)
_COMPARED_TIMING_METRICS: tuple[str, ...] = ("personal_year", "personal_month", "personal_day")

#: V1.5 Epic F — the subset of compared metrics that get a knowledge-sourced
#: qualitative insight. Timing metrics (personal year/month/day) describe a moment,
#: not a personality trait, so they carry no "relationships" theme in the knowledge
#: package and are intentionally excluded here.
_INSIGHT_METRICS: tuple[str, ...] = ("life_path", "expression", "soul_urge", "personality")

REPO_ROOT = Path(__file__).resolve().parents[5]
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"


def _extract(profile: dict[str, Any], section: str, metric_id: str) -> dict[str, Any] | None:
    section_data = profile.get(section)
    if not isinstance(section_data, dict):
        return None
    value = section_data.get(metric_id)
    return value if isinstance(value, dict) else None


def build_relationship_comparison(
    profile_a: dict[str, Any], profile_b: dict[str, Any]
) -> dict[str, Any]:
    """Deterministic side-by-side comparison. No compatibility percentage — that is
    RESERVED_UNFROZEN in V1 (canon-spec.md §33)."""
    comparisons: dict[str, Any] = {}

    for section, metric_id in _COMPARED_METRICS:
        a = _extract(profile_a, section, metric_id)
        b = _extract(profile_b, section, metric_id)
        comparisons[metric_id] = {
            "person_a": {"display_value": a["display_value"] if a else None},
            "person_b": {"display_value": b["display_value"] if b else None},
            "match": bool(a and b and a["effective_value"] == b["effective_value"]),
        }

    timing_a = profile_a.get("timing", {})
    timing_b = profile_b.get("timing", {})
    for metric_id in _COMPARED_TIMING_METRICS:
        a = timing_a.get(metric_id)
        b = timing_b.get(metric_id)
        comparisons[metric_id] = {
            "person_a": {"display_value": a["display_value"] if a else None},
            "person_b": {"display_value": b["display_value"] if b else None},
            "match": bool(a and b and a["effective_value"] == b["effective_value"]),
        }

    return comparisons


def build_relationship_insights(
    profile_a: dict[str, Any], profile_b: dict[str, Any]
) -> list[dict[str, Any]]:
    """V1.5 Epic F: structured, knowledge-sourced qualitative notes for each core
    metric — never a compatibility percentage or numeric match score (canon-spec.md
    §33, RESERVED_UNFROZEN). Every theme is quoted verbatim from
    `knowledge/numbers/*.yaml` / `knowledge/master-numbers/*.yaml`'s existing
    ``relationships`` field (see `knowledge/relationships/README.md`) — this function
    composes, it does not invent new interpretive text.

    A metric whose knowledge entry is missing (should not happen for a validated
    knowledge package) is skipped rather than raising, since a comparison must still
    render even if one exotic metric's content is absent.
    """
    knowledge = load_knowledge_base(KNOWLEDGE_ROOT)
    insights: list[dict[str, Any]] = []

    for _section, metric_id in _COMPARED_METRICS:
        if metric_id not in _INSIGHT_METRICS:
            continue
        a = _extract(profile_a, "core_numbers", metric_id)
        b = _extract(profile_b, "core_numbers", metric_id)
        if a is None or b is None:
            continue
        value_a = int(a["effective_value"])
        value_b = int(b["effective_value"])
        try:
            knowledge_a = knowledge.number(value_a)
            knowledge_b = knowledge.number(value_b)
        except KeyError:
            continue

        insights.append(
            {
                "metric_id": metric_id,
                "person_a_number": value_a,
                "person_b_number": value_b,
                "shared_number": value_a == value_b,
                "person_a_relationship_themes": list(knowledge_a.relationships),
                "person_b_relationship_themes": list(knowledge_b.relationships),
                "knowledge_refs": sorted({f"numbers/{value_a}", f"numbers/{value_b}"}),
            }
        )

    return insights
