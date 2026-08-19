from __future__ import annotations

from typing import Any

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
