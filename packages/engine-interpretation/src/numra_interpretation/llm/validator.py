"""The per-claim Report Numerical Linter.

Given generated text/structured output that may contain ``{{metric:life_path}}``-style
placeholders and/or explicit `NumericClaim`s, this verifies every claim's
``display_value`` exactly matches the `CanonicalProfile` it is supposed to describe, and
that every placeholder references a known ``metric_id``. Any mismatch raises
`InvalidReportSection` — there is no silent correction, no "closest match", no rounding.

Scope: this validates *individual* claims/placeholders against the profile's
`core_numbers` and `timing` sections (per the phase-3 task). A fuller multi-section
report linter (cross-section consistency, narrative-level checks) is a later phase.
"""

from __future__ import annotations

import re

from numra_interpretation.errors import InvalidReportSection
from numra_interpretation.llm.types import NumericClaim
from numra_numerology.models.profile import CanonicalProfile

__all__ = [
    "build_metric_display_value_index",
    "extract_placeholder_metric_ids",
    "validate_generation_result",
    "validate_numeric_claims",
]

_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*metric\s*:\s*([a-zA-Z0-9_]+)\s*\}\}")

#: `core_numbers` fields that are `CalculationMetric` instances with a `metric_id` +
#: `display_value`; see `composer.CORE_METRIC_IDS` for the same scoping rationale.
_CORE_METRIC_IDS: tuple[str, ...] = (
    "life_path",
    "birthday",
    "attitude",
    "expression",
    "soul_urge",
    "personality",
    "maturity",
    "balance",
)

#: `timing` fields that carry a `display_value` directly comparable to a claim.
_TIMING_METRIC_IDS: tuple[str, ...] = ("personal_year", "personal_month", "personal_day")


def build_metric_display_value_index(profile: CanonicalProfile) -> dict[str, str]:
    """Build a ``metric_id -> display_value`` lookup from a `CanonicalProfile`'s
    `core_numbers` and `timing` sections — the ground truth for claim validation."""
    index: dict[str, str] = {}
    for metric_id in _CORE_METRIC_IDS:
        index[metric_id] = getattr(profile.core_numbers, metric_id).display_value
    for metric_id in _TIMING_METRIC_IDS:
        index[metric_id] = getattr(profile.timing, metric_id).display_value
    # universal_year is a bare ReductionResult (no metric_id of its own on the model),
    # but it is a legitimate, known timing fact a report may cite.
    index["universal_year"] = profile.timing.universal_year.display_value
    return index


def extract_placeholder_metric_ids(text: str) -> tuple[str, ...]:
    """Extract every ``{{metric:ID}}`` placeholder's ``ID`` from free text, in order of
    first appearance, deduplicated."""
    seen: dict[str, None] = {}
    for match in _PLACEHOLDER_PATTERN.finditer(text):
        seen.setdefault(match.group(1), None)
    return tuple(seen)


def validate_numeric_claims(claims: tuple[NumericClaim, ...], profile: CanonicalProfile) -> None:
    """Raise `InvalidReportSection` if any claim references an unknown ``metric_id`` or
    a ``display_value`` that does not exactly match the profile."""
    index = build_metric_display_value_index(profile)
    for claim in claims:
        if claim.metric_id not in index:
            raise InvalidReportSection(f"Unknown metric_id in numeric claim: {claim.metric_id!r}")
        actual = index[claim.metric_id]
        if claim.display_value != actual:
            raise InvalidReportSection(
                f"Numeric claim mismatch for metric_id={claim.metric_id!r}: "
                f"claimed display_value={claim.display_value!r}, "
                f"canonical display_value={actual!r}"
            )


def validate_generation_result(
    text: str, claims: tuple[NumericClaim, ...], profile: CanonicalProfile
) -> None:
    """Full per-claim validation: checks `claims` against the profile (see
    `validate_numeric_claims`) and additionally checks every ``{{metric:ID}}``
    placeholder found in ``text`` references a known ``metric_id``."""
    index = build_metric_display_value_index(profile)
    for metric_id in extract_placeholder_metric_ids(text):
        if metric_id not in index:
            raise InvalidReportSection(
                f"Unknown metric_id referenced by placeholder: {{{{metric:{metric_id}}}}}"
            )
    validate_numeric_claims(claims, profile)
