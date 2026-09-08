"""specs/v2/checkin-spec.md Section 20 (Deterministic analysis) -- pure, DB-free
numeric aggregation for one `RelationshipCheckin` round. NO LLM import anywhere in
this module: gap/direction/trend/delta/sample-size are computed here, not by the
LLM -- the LLM (out of scope for this PR) only ever explains this already-computed
JSON afterwards, never recomputes or overrides it.

Every function takes plain values/lists in and returns plain dicts out -- no
`AsyncSession`, no ORM objects -- so it is unit-testable without a database (see
tests/unit/test_checkin_analysis_service.py).
"""

from __future__ import annotations

from collections.abc import Sequence

#: How many of the most recent `absolute_gap` values feed `rolling_trend` (and cap
#: the "recent" window used by `historical_delta`, see `_split_for_historical_delta`).
ROLLING_WINDOW = 5

#: A round only carries `sufficient_evidence=True` once at least this many rounds
#: (current included) exist for the same (workspace, semantic_key,
#: checkin_template_version) series. Deliberately its own constant here, NOT coupled
#: to specs/v2/evidence-policy.md's `EvidencePolicy` thresholds -- 3 rounds are
#: enough to distinguish a first direction from noise in a pure time-series smoothing
#: context; `EvidencePolicy` governs a materially different question (correlation
#: claims across profiles), so reusing its number would be a false coupling.
MIN_SAMPLE_SIZE_FOR_TREND = 3


def _mean(values: Sequence[int | float]) -> float:
    return sum(values) / len(values)


def _split_for_historical_delta(
    all_gaps: list[int],
) -> tuple[list[int], list[int]] | None:
    """Splits the chronological gap series into a "recent" window and the "before"
    remainder for `historical_delta`. The recent window is half the series (floor),
    capped at `ROLLING_WINDOW` and at least 1 -- `None` is returned exactly when there
    is no non-empty "before" remainder, i.e. fewer than 2 rounds total."""
    sample_size = len(all_gaps)
    if sample_size < 2:
        return None
    recent_n = max(1, min(ROLLING_WINDOW, sample_size // 2))
    recent = all_gaps[-recent_n:]
    before = all_gaps[:-recent_n]
    if not before:
        return None
    return recent, before


def compute_dimension_result(
    *, value_a: int, value_b: int, historical_gaps: list[int]
) -> dict[str, object]:
    """One dimension's analysis for the current round.

    `historical_gaps` is the chronologically ordered (oldest first) list of
    `absolute_gap` values from PRIOR analyzed rounds of the SAME
    (workspace, semantic_key, checkin_template_version) series -- the caller
    (services/checkin_service.py) is responsible for that segmentation; this function
    only aggregates whatever list it is given.
    """
    absolute_gap = abs(value_a - value_b)
    all_gaps = [*historical_gaps, absolute_gap]
    sample_size = len(all_gaps)

    if not historical_gaps:
        direction = "NO_PRIOR_DATA"
    else:
        previous_gap = historical_gaps[-1]
        if absolute_gap < previous_gap:
            direction = "CONVERGING"
        elif absolute_gap > previous_gap:
            direction = "DIVERGING"
        else:
            direction = "STABLE"

    rolling_window = min(sample_size, ROLLING_WINDOW)
    rolling_trend = _mean(all_gaps[-rolling_window:])

    split = _split_for_historical_delta(all_gaps)
    historical_delta = _mean(split[0]) - _mean(split[1]) if split is not None else None

    return {
        "absolute_gap": absolute_gap,
        "direction": direction,
        "rolling_trend": rolling_trend,
        "sample_size": sample_size,
        "historical_delta": historical_delta,
        "sufficient_evidence": sample_size >= MIN_SAMPLE_SIZE_FOR_TREND,
    }


def compute_checkin_analysis(
    *,
    dimension_values: dict[str, tuple[int, int]],
    historical_gaps_by_key: dict[str, list[int]],
) -> dict[str, dict[str, object]]:
    """Computes the full `CheckinAnalysis.result_json` for one round.

    `dimension_values`: `{semantic_key: (value_a, value_b)}` for every active
    dimension both members submitted this round.
    `historical_gaps_by_key`: `{semantic_key: [prior absolute_gap, ...]}`, already
    segmented by `checkin_template_version` by the caller.
    """
    return {
        semantic_key: compute_dimension_result(
            value_a=value_a,
            value_b=value_b,
            historical_gaps=historical_gaps_by_key.get(semantic_key, []),
        )
        for semantic_key, (value_a, value_b) in dimension_values.items()
    }


__all__ = [
    "MIN_SAMPLE_SIZE_FOR_TREND",
    "ROLLING_WINDOW",
    "compute_checkin_analysis",
    "compute_dimension_result",
]
