"""PR-V2-11 -- reine Rechenlogik des Evidence Layer
(services/evidence_analysis_service.py). Kein DB-Zugriff, keine App-Fixture: die
Funktion nimmt Werte und gibt Werte zurueck.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from numra_api.services.evidence_analysis_service import (
    BUCKET_SPACE_SIZE,
    EvidencePolicySnapshot,
    EvidenceSample,
    compute_evidence_result,
)

pytestmark = pytest.mark.unit

_START = dt.date(2026, 1, 1)


def _policy(**overrides: object) -> EvidencePolicySnapshot:
    defaults: dict[str, object] = {
        "version": 1,
        "minimum_total_sample_count": 30,
        "minimum_sample_count_per_bucket": 5,
        "minimum_observation_window_days": 45,
        "missing_data_handling": "EXCLUDE",
        "outlier_policy": "WINSORIZE_P95",
        "multiple_comparison_protection": "NONE",
        "effect_size_threshold": Decimal("0.500"),
        "confidence_category_thresholds": {"LOW": 0.5, "MEDIUM": 0.65, "HIGH": 0.8},
    }
    defaults.update(overrides)
    return EvidencePolicySnapshot(**defaults)  # type: ignore[arg-type]


def _samples(
    count: int, *, bucket_every: int, bucket_value: int, high: int, low: int
) -> list[EvidenceSample]:
    """`count` aufeinanderfolgende Tage; jeder `bucket_every`-te Tag liegt im Bucket
    und traegt `high`, alle anderen `low`."""
    return [
        EvidenceSample(
            entry_date=_START + dt.timedelta(days=index),
            bucket_value=bucket_value if index % bucket_every == 0 else bucket_value + 1,
            metric_value=high if index % bucket_every == 0 else low,
        )
        for index in range(count)
    ]


def test_strong_separation_yields_high_confidence_and_statement() -> None:
    result = compute_evidence_result(
        samples=_samples(60, bucket_every=9, bucket_value=5, high=9, low=3),
        policy=_policy(),
        correlation_target="PERSONAL_DAY",
        correlation_target_value=5,
        metric_label="Energie",
    )

    assert result["confidence_category"] == "HIGH"
    assert result["sample_size"] == 60
    assert result["observation_window_days"] == 60
    assert result["bucket_mean"] == 9.0
    statement = result["statement_text"]
    assert isinstance(statement, str)
    # Die drei Pflicht-Qualifier stehen im Text selbst, nicht nur im JSON.
    assert "60 Tage" in statement
    assert "HIGH" in statement
    assert "keine Ursache" in statement


def test_too_few_samples_is_no_reliable_pattern_not_an_error() -> None:
    result = compute_evidence_result(
        samples=_samples(10, bucket_every=2, bucket_value=5, high=9, low=3),
        policy=_policy(),
        correlation_target="PERSONAL_DAY",
        correlation_target_value=5,
        metric_label="Energie",
    )

    assert result["confidence_category"] == "NO_RELIABLE_PATTERN"
    assert result["statement_text"] is None
    assert result["effect_size"] is None
    # Stichprobengroesse bleibt gefuellt -- der Nutzer soll sehen, wie weit er von
    # einer belastbaren Aussage entfernt ist.
    assert result["sample_size"] == 10


def test_too_few_samples_in_bucket_is_no_reliable_pattern() -> None:
    samples = _samples(60, bucket_every=61, bucket_value=5, high=9, low=3)
    result = compute_evidence_result(
        samples=samples,
        policy=_policy(),
        correlation_target="PERSONAL_DAY",
        correlation_target_value=5,
        metric_label="Energie",
    )
    assert result["sample_size"] == 60
    assert result["confidence_category"] == "NO_RELIABLE_PATTERN"


def test_observation_window_too_short_is_no_reliable_pattern() -> None:
    """40 Eintraege in 40 Tagen erfuellen die Stichprobengroesse, nicht aber das
    Mindest-Beobachtungsfenster von 45 Tagen."""
    result = compute_evidence_result(
        samples=_samples(40, bucket_every=5, bucket_value=5, high=9, low=3),
        policy=_policy(),
        correlation_target="PERSONAL_DAY",
        correlation_target_value=5,
        metric_label="Energie",
    )
    assert result["observation_window_days"] == 40
    assert result["confidence_category"] == "NO_RELIABLE_PATTERN"


def test_constant_metric_has_no_pattern_regardless_of_sample_size() -> None:
    result = compute_evidence_result(
        samples=_samples(60, bucket_every=9, bucket_value=5, high=7, low=7),
        policy=_policy(),
        correlation_target="PERSONAL_DAY",
        correlation_target_value=5,
        metric_label="Energie",
    )
    assert result["confidence_category"] == "NO_RELIABLE_PATTERN"


def test_effect_below_threshold_is_no_reliable_pattern() -> None:
    """Eine reale, aber winzige Abweichung wird bewusst nicht behauptet."""
    samples = [
        EvidenceSample(
            entry_date=_START + dt.timedelta(days=index),
            bucket_value=5 if index % 9 == 0 else 6,
            metric_value=(6 if index % 9 == 0 else 5) if index % 2 == 0 else 4,
        )
        for index in range(60)
    ]
    result = compute_evidence_result(
        samples=samples,
        policy=_policy(effect_size_threshold=Decimal("2.000")),
        correlation_target="PERSONAL_DAY",
        correlation_target_value=5,
        metric_label="Energie",
    )
    assert result["confidence_category"] == "NO_RELIABLE_PATTERN"


def test_missing_values_are_excluded_from_sample_size() -> None:
    samples = _samples(60, bucket_every=9, bucket_value=5, high=9, low=3)
    blanked = [
        EvidenceSample(
            entry_date=sample.entry_date,
            bucket_value=sample.bucket_value,
            metric_value=None if index % 3 == 1 else sample.metric_value,
        )
        for index, sample in enumerate(samples)
    ]
    result = compute_evidence_result(
        samples=blanked,
        policy=_policy(),
        correlation_target="PERSONAL_DAY",
        correlation_target_value=5,
        metric_label="Energie",
    )
    assert result["sample_size"] == 40
    assert result["confidence_category"] == "HIGH"


def test_bonferroni_raises_the_required_effect_size() -> None:
    """Mit `sqrt(BUCKET_SPACE_SIZE)` als Faktor liegt die Schwelle so hoch, dass
    derselbe Datensatz nicht mehr durchgeht -- Policy Version 1 nutzt NONE."""
    samples = _samples(60, bucket_every=9, bucket_value=5, high=9, low=3)
    assert BUCKET_SPACE_SIZE == 12

    without = compute_evidence_result(
        samples=samples,
        policy=_policy(effect_size_threshold=Decimal("1.000")),
        correlation_target="PERSONAL_DAY",
        correlation_target_value=5,
        metric_label="Energie",
    )
    with_protection = compute_evidence_result(
        samples=samples,
        policy=_policy(
            effect_size_threshold=Decimal("1.000"),
            multiple_comparison_protection="BONFERRONI",
        ),
        correlation_target="PERSONAL_DAY",
        correlation_target_value=5,
        metric_label="Energie",
    )
    assert without["confidence_category"] == "HIGH"
    assert with_protection["confidence_category"] == "NO_RELIABLE_PATTERN"


def test_winsorize_caps_a_single_extreme_day_without_dropping_it() -> None:
    """Der Ausreisser wird gekappt, verschwindet aber nicht aus der Stichprobe --
    `sample_size` bleibt ehrlich."""
    samples = [
        EvidenceSample(
            entry_date=_START + dt.timedelta(days=index),
            bucket_value=5 if index % 9 == 0 else 6,
            metric_value=10000 if index == 3 else (9 if index % 9 == 0 else 3),
        )
        for index in range(60)
    ]
    winsorized = compute_evidence_result(
        samples=samples,
        policy=_policy(),
        correlation_target="PERSONAL_DAY",
        correlation_target_value=5,
        metric_label="Energie",
    )
    raw = compute_evidence_result(
        samples=samples,
        policy=_policy(outlier_policy="NONE"),
        correlation_target="PERSONAL_DAY",
        correlation_target_value=5,
        metric_label="Energie",
    )
    assert winsorized["sample_size"] == raw["sample_size"] == 60
    assert winsorized["confidence_category"] == "HIGH"
    # Ohne Kappung reisst der eine Extremtag die Baseline-Streuung so weit auf, dass
    # der echte Bucket-Effekt unter die Schwelle faellt.
    assert raw["confidence_category"] == "NO_RELIABLE_PATTERN"


def test_interpolate_none_counts_gap_days_towards_the_window() -> None:
    """Der einzige beobachtbare Unterschied der beiden `missing_data_handling`-Modi:
    interpoliert wird in keinem von beiden."""
    samples = [
        EvidenceSample(
            entry_date=_START + dt.timedelta(days=index),
            bucket_value=5,
            metric_value=None if index >= 30 else 5,
        )
        for index in range(60)
    ]
    excluded = compute_evidence_result(
        samples=samples,
        policy=_policy(),
        correlation_target="PERSONAL_DAY",
        correlation_target_value=5,
        metric_label="Energie",
    )
    interpolate_none = compute_evidence_result(
        samples=samples,
        policy=_policy(missing_data_handling="INTERPOLATE_NONE"),
        correlation_target="PERSONAL_DAY",
        correlation_target_value=5,
        metric_label="Energie",
    )
    assert excluded["observation_window_days"] == 30
    assert interpolate_none["observation_window_days"] == 60
    assert excluded["sample_size"] == interpolate_none["sample_size"] == 30
