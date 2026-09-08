"""specs/v2/checkin-spec.md Section 20 -- pure aggregation unit tests, no DB, no
LLM. Covers absolute_gap/direction/rolling_trend/historical_delta/sample_size across
1, 2, 5+ round histories, the sufficient_evidence 2-vs-3 boundary, and
checkin_template_version segmentation (via the caller-supplied historical_gaps
list -- this module never queries the DB itself).
"""

from __future__ import annotations

import pytest

from numra_api.services.checkin_analysis_service import (
    MIN_SAMPLE_SIZE_FOR_TREND,
    ROLLING_WINDOW,
    compute_checkin_analysis,
    compute_dimension_result,
)

pytestmark = pytest.mark.unit


def test_first_round_has_no_prior_data() -> None:
    result = compute_dimension_result(value_a=8, value_b=5, historical_gaps=[])
    assert result["absolute_gap"] == 3
    assert result["direction"] == "NO_PRIOR_DATA"
    assert result["sample_size"] == 1
    assert result["rolling_trend"] == 3
    assert result["historical_delta"] is None
    assert result["sufficient_evidence"] is False


def test_second_round_converging_computes_historical_delta() -> None:
    # prior gap 5, current gap 2 -> converging; sample_size 2 -> delta computable.
    result = compute_dimension_result(value_a=6, value_b=4, historical_gaps=[5])
    assert result["absolute_gap"] == 2
    assert result["direction"] == "CONVERGING"
    assert result["sample_size"] == 2
    assert result["historical_delta"] == 2 - 5
    assert result["sufficient_evidence"] is False


def test_second_round_diverging() -> None:
    result = compute_dimension_result(value_a=9, value_b=2, historical_gaps=[3])
    assert result["absolute_gap"] == 7
    assert result["direction"] == "DIVERGING"


def test_stable_direction_on_equal_gap() -> None:
    result = compute_dimension_result(value_a=7, value_b=3, historical_gaps=[4])
    assert result["absolute_gap"] == 4
    assert result["direction"] == "STABLE"


def test_sufficient_evidence_boundary_two_vs_three_rounds() -> None:
    two_rounds = compute_dimension_result(value_a=5, value_b=5, historical_gaps=[1])
    assert two_rounds["sample_size"] == 2
    assert two_rounds["sufficient_evidence"] is False

    three_rounds = compute_dimension_result(value_a=5, value_b=5, historical_gaps=[1, 2])
    assert three_rounds["sample_size"] == 3
    assert three_rounds["sufficient_evidence"] is True
    assert three_rounds["sample_size"] >= MIN_SAMPLE_SIZE_FOR_TREND


def test_five_plus_rounds_rolling_trend_caps_at_window() -> None:
    # 6 prior gaps + current = 7 total, rolling_trend must average only the last
    # ROLLING_WINDOW (5) values, not all 7.
    historical_gaps = [10, 10, 1, 2, 3, 4]
    result = compute_dimension_result(value_a=5, value_b=0, historical_gaps=historical_gaps)
    all_gaps = [*historical_gaps, 5]
    assert result["sample_size"] == 7
    assert len(all_gaps[-ROLLING_WINDOW:]) == ROLLING_WINDOW
    expected_trend = sum(all_gaps[-ROLLING_WINDOW:]) / ROLLING_WINDOW
    assert result["rolling_trend"] == expected_trend
    assert result["sufficient_evidence"] is True


def test_historical_delta_none_for_single_round_only() -> None:
    result = compute_dimension_result(value_a=1, value_b=1, historical_gaps=[])
    assert result["sample_size"] == 1
    assert result["historical_delta"] is None


def test_compute_checkin_analysis_segments_per_dimension_and_never_mixes_keys() -> None:
    dimension_values = {
        "closeness": (8, 6),
        "communication": (5, 5),
    }
    historical_gaps_by_key = {
        "closeness": [1, 1],
        # "communication" intentionally has no history -- must not borrow
        # "closeness"'s history (segmentation correctness).
    }
    result = compute_checkin_analysis(
        dimension_values=dimension_values, historical_gaps_by_key=historical_gaps_by_key
    )
    assert set(result.keys()) == {"closeness", "communication"}
    assert result["closeness"]["sample_size"] == 3
    assert result["communication"]["sample_size"] == 1
    assert result["communication"]["direction"] == "NO_PRIOR_DATA"


def test_two_series_different_template_versions_never_mix() -> None:
    """Simulates what services/checkin_service.py must guarantee: the
    historical_gaps list passed in is already filtered by checkin_template_version,
    so a v1 series and a v2 series for the same semantic_key never share history."""
    v1_result = compute_dimension_result(value_a=9, value_b=1, historical_gaps=[8, 8, 8])
    v2_result = compute_dimension_result(value_a=9, value_b=1, historical_gaps=[])

    assert v1_result["sample_size"] == 4
    assert v1_result["direction"] == "STABLE"
    assert v2_result["sample_size"] == 1
    assert v2_result["direction"] == "NO_PRIOR_DATA"
