"""PR-V2-11 -- specs/v2/evidence-policy.md: deterministische Korrelationsrechnung
fuer den Evidence Layer.

Spiegelt bewusst die Disziplin von ``checkin_analysis_service.py``: reine
Funktionen, einfache Werte rein, einfache Werte raus. KEIN ``AsyncSession``, KEIN
ORM-Objekt, KEIN LLM-Import in diesem Modul. Stichprobengroesse, Beobachtungs-
zeitraum, Baseline, Bucket-Mittelwert, Effektstaerke und Konfidenzkategorie
entstehen hier -- ein LLM erklaert diese Zahlen spaeter allenfalls, es berechnet
sie nie und ueberschreibt sie nie (specs/v2/evidence-policy.md: "never computed
by the LLM").

Kein eigenes Package: die Rechnung braucht ausser der Standardbibliothek nichts,
und sie ist -- anders als ``numra_numerology`` -- keine Kanon-Berechnung, sondern
Auswertung getrackter Nutzerdaten. Die kanonischen Personal-Day/Month/Year-Werte
kommen fertig als ``bucket_value`` herein (der Aufrufer holt sie ueber
``numra_numerology.timing.lookup``), damit dieses Modul den Kanon strukturell gar
nicht neu erfinden kann.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from decimal import Decimal

__all__ = [
    "BUCKET_SPACE_SIZE",
    "METRIC_LABELS_DE",
    "STANDARD_METRIC_KEYS",
    "TARGET_LABELS_DE",
    "EvidencePolicySnapshot",
    "EvidenceSample",
    "compute_evidence_result",
]

#: Die fuenf festen Spalten auf ``LifeTrackingEntry``. Alles andere ist eine
#: ``CustomMetricDefinition`` und lebt in ``LifeTrackingMetricValue``.
STANDARD_METRIC_KEYS: tuple[str, ...] = ("mood", "energy", "sleep", "stress", "focus")

METRIC_LABELS_DE: dict[str, str] = {
    "mood": "Stimmung",
    "energy": "Energie",
    "sleep": "Schlafqualitaet",
    "stress": "Stressniveau",
    "focus": "Fokus",
}

TARGET_LABELS_DE: dict[str, str] = {
    "PERSONAL_DAY": "Personal-Day",
    "PERSONAL_MONTH": "Personal-Month",
    "PERSONAL_YEAR": "Personal-Year",
}

#: Wie viele verschiedene Werte ein kanonischer Personal-Day/Month/Year-Wert
#: annehmen kann: die Wurzeln 1..9 plus die Master Numbers 11/22/33
#: (``numra_numerology.models.reduction.MASTER_NUMBERS``). Das ist die Anzahl
#: paralleler Vergleiche, gegen die ``BONFERRONI`` korrigiert.
BUCKET_SPACE_SIZE = 12

#: Nur zur Anzeige gerundet -- die Gate-Entscheidungen unten laufen immer auf den
#: ungerundeten Werten, damit Rundung nie eine Schwelle kippt.
_DISPLAY_PRECISION = 2


@dataclass(frozen=True)
class EvidencePolicySnapshot:
    """Die Felder einer ``EvidencePolicy``-Zeile als reine Werte. Der Aufrufer
    (``evidence_service.py``) baut das aus dem ORM-Objekt, damit hier kein
    SQLAlchemy-Typ auftaucht."""

    version: int
    minimum_total_sample_count: int
    minimum_sample_count_per_bucket: int
    minimum_observation_window_days: int
    missing_data_handling: str
    outlier_policy: str
    multiple_comparison_protection: str
    effect_size_threshold: Decimal
    confidence_category_thresholds: dict[str, float]


@dataclass(frozen=True)
class EvidenceSample:
    """Ein Tracking-Tag. ``metric_value is None`` heisst: der Eintrag existiert,
    aber die untersuchte Metrik wurde an dem Tag nicht erfasst -- was damit
    passiert, entscheidet ``missing_data_handling``."""

    entry_date: dt.date
    bucket_value: int
    metric_value: int | None


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _percentile(sorted_values: list[float], fraction: float) -> float:
    """Lineare Interpolation zwischen den beiden benachbarten Rangplaetzen (Typ-7,
    die Konvention von numpy/R). Deterministisch, keine Abhaengigkeit noetig."""
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = fraction * (len(sorted_values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _winsorize(values: list[float]) -> list[float]:
    """Kappt an P5/P95, statt Ausreisser zu verwerfen -- die Stichprobengroesse
    bleibt dadurch ehrlich (ein verworfener Tag wuerde ``sample_size`` senken und
    das Ergebnis doppelt bestrafen)."""
    ordered = sorted(values)
    low = _percentile(ordered, 0.05)
    high = _percentile(ordered, 0.95)
    return [min(max(value, low), high) for value in values]


def _population_stdev(values: list[float], mean: float) -> float:
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _effective_effect_size_threshold(policy: EvidencePolicySnapshot) -> float:
    """``BONFERRONI`` hebt die geforderte Effektstaerke an, statt ein
    Signifikanzniveau zu korrigieren: dieser PR rechnet bewusst ohne p-Werte, also
    gibt es kein Alpha zum Teilen. Skaliert wird mit ``sqrt(k)`` ueber die
    ``BUCKET_SPACE_SIZE`` parallelen Bucket-Vergleiche -- bewusst konservativ und
    ausdruecklich eine Naeherung, kein exaktes Bonferroni-Aequivalent. Policy
    Version 1 setzt ``NONE``, es haengt also kein ausgeliefertes Ergebnis daran."""
    threshold = float(policy.effect_size_threshold)
    if policy.multiple_comparison_protection == "BONFERRONI":
        return threshold * math.sqrt(BUCKET_SPACE_SIZE)
    return threshold


def _observation_window_days(samples: list[EvidenceSample], usable: list[EvidenceSample]) -> int:
    """``EXCLUDE``: der Zeitraum spannt nur ueber Tage mit tatsaechlichem Messwert.
    ``INTERPOLATE_NONE``: der Zeitraum spannt ueber alle Eintraege -- ein Tag ohne
    Messwert zaehlt zur Beobachtungsdauer, es wird aber nie ein Wert erfunden. Das
    ist der einzige beobachtbare Unterschied der beiden Modi; interpoliert wird in
    keinem von beiden."""
    if not usable:
        return 0
    dates = [sample.entry_date for sample in samples]
    return (max(dates) - min(dates)).days + 1


def _confidence_category(effect_size: float, thresholds: dict[str, float]) -> str:
    """Hoechste erreichte Stufe gewinnt. Fehlt eine Stufe in der Policy, gilt sie
    als nicht erreichbar -- die Policy ist die einzige Quelle der Schwellen."""
    magnitude = abs(effect_size)
    for category in ("HIGH", "MEDIUM", "LOW"):
        threshold = thresholds.get(category)
        if threshold is not None and magnitude >= threshold:
            return category
    return "NO_RELIABLE_PATTERN"


def _no_reliable_pattern(
    sample_size: int, observation_window_days: int, version: int
) -> dict[str, object]:
    """Gueltiges Ergebnis, kein Fehlerzustand (specs/v2/evidence-policy.md).
    ``statement_text`` ist ``None`` -- es gibt schlicht nichts zu behaupten."""
    return {
        "sample_size": sample_size,
        "observation_window_days": observation_window_days,
        "confidence_category": "NO_RELIABLE_PATTERN",
        "effect_size": None,
        "baseline_mean": None,
        "bucket_mean": None,
        "statement_text": None,
        "evidence_policy_version": version,
    }


def _render_statement(
    *,
    metric_label: str,
    target_label: str,
    correlation_target_value: int,
    bucket_mean: float,
    baseline_mean: float,
    sample_size: int,
    observation_window_days: int,
    confidence_category: str,
) -> str:
    """Fester Template-String, nie LLM-generiert. Die drei Pflicht-Qualifier sind
    strukturell eingebettet, nicht angehaengt -- deshalb kann
    ``lint_structured_statement`` sie hier gar nicht vermissen, solange dieses
    Template die Quelle ist. Der Schlusssatz haelt die Aussage explizit
    korrelational (specs/v2/evidence-policy.md: nie kausal)."""
    direction = "hoeher" if bucket_mean >= baseline_mean else "niedriger"
    return (
        f"An den bislang beobachteten {target_label}-{correlation_target_value}-Tagen lag "
        f"deine gemessene {metric_label} im Mittel bei "
        f"{bucket_mean:.{_DISPLAY_PRECISION}f} und damit {direction} als deine "
        f"persoenliche Baseline von {baseline_mean:.{_DISPLAY_PRECISION}f}. "
        f"Stichprobe: {sample_size} Tage, Beobachtungszeitraum: "
        f"{observation_window_days} Tage, Konfidenz: {confidence_category}. "
        f"Das ist ein beobachteter Zusammenhang in deinen eigenen Daten, keine Ursache."
    )


def compute_evidence_result(
    *,
    samples: list[EvidenceSample],
    policy: EvidencePolicySnapshot,
    correlation_target: str,
    correlation_target_value: int,
    metric_label: str,
) -> dict[str, object]:
    """Berechnet ein vollstaendiges ``EvidenceResult`` fuer genau einen
    (Metrik, Correlation-Target, Target-Wert)-Vergleich.

    ``samples`` sind alle Tracking-Tage der Person -- ungefiltert und chronologisch
    egal, die Funktion filtert selbst. Rueckgabe ist genau die Form, die
    ``numra_interpretation.report.evidence_linter.lint_structured_statement``
    erwartet und die als ``PatternAnalysis.result_json`` persistiert wird.

    ``NO_RELIABLE_PATTERN`` ist der reglaere Rueckgabewert, sobald eine der
    Policy-Mindestanforderungen nicht erfuellt ist -- nie eine Exception."""
    usable = [sample for sample in samples if sample.metric_value is not None]
    sample_size = len(usable)
    observation_window_days = _observation_window_days(
        samples if policy.missing_data_handling == "INTERPOLATE_NONE" else usable, usable
    )

    if (
        sample_size < policy.minimum_total_sample_count
        or observation_window_days < policy.minimum_observation_window_days
    ):
        return _no_reliable_pattern(sample_size, observation_window_days, policy.version)

    bucket_indices = [
        index
        for index, sample in enumerate(usable)
        if sample.bucket_value == correlation_target_value
    ]
    if len(bucket_indices) < policy.minimum_sample_count_per_bucket:
        return _no_reliable_pattern(sample_size, observation_window_days, policy.version)

    raw_values = [
        float(sample.metric_value) for sample in usable if sample.metric_value is not None
    ]
    values = _winsorize(raw_values) if policy.outlier_policy == "WINSORIZE_P95" else raw_values

    baseline_mean = _mean(values)
    bucket_mean = _mean([values[index] for index in bucket_indices])

    # Standardisierte Mittelwertdifferenz gegen die persoenliche Baseline-Streuung
    # (Cohen-d-Form). Eine Streuung von 0 heisst: die Metrik ist ueber den ganzen
    # Zeitraum konstant -- dann gibt es keinen Unterschied zu berichten, egal wie
    # gross die Stichprobe ist.
    baseline_stdev = _population_stdev(values, baseline_mean)
    if baseline_stdev == 0.0:
        return _no_reliable_pattern(sample_size, observation_window_days, policy.version)

    effect_size = (bucket_mean - baseline_mean) / baseline_stdev

    if abs(effect_size) < _effective_effect_size_threshold(policy):
        return _no_reliable_pattern(sample_size, observation_window_days, policy.version)

    confidence_category = _confidence_category(effect_size, policy.confidence_category_thresholds)
    if confidence_category == "NO_RELIABLE_PATTERN":
        return _no_reliable_pattern(sample_size, observation_window_days, policy.version)

    rounded_bucket_mean = round(bucket_mean, _DISPLAY_PRECISION)
    rounded_baseline_mean = round(baseline_mean, _DISPLAY_PRECISION)
    return {
        "sample_size": sample_size,
        "observation_window_days": observation_window_days,
        "confidence_category": confidence_category,
        "effect_size": round(effect_size, 3),
        "baseline_mean": rounded_baseline_mean,
        "bucket_mean": rounded_bucket_mean,
        "statement_text": _render_statement(
            metric_label=metric_label,
            target_label=TARGET_LABELS_DE[correlation_target],
            correlation_target_value=correlation_target_value,
            bucket_mean=rounded_bucket_mean,
            baseline_mean=rounded_baseline_mean,
            sample_size=sample_size,
            observation_window_days=observation_window_days,
            confidence_category=confidence_category,
        ),
        "evidence_policy_version": policy.version,
    }
