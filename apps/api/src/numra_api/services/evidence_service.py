"""PR-V2-11 -- DB-Orchestrierung fuer den Evidence Layer
(specs/v2/evidence-policy.md).

Arbeitsteilung, bewusst wie bei `checkin_service.py` / `checkin_analysis_service.py`:
dieses Modul laedt Policy, Metrik-Definition und Tracking-Eintraege, leitet die
kanonischen Personal-Day/Month/Year-Werte pro Tag aus `numra_numerology.timing.
lookup` ab und uebergibt reine Werte an `evidence_analysis_service.py`. Es rechnet
selbst nichts und kennt keine Schwellen -- die stehen ausschliesslich in der
aktiven `EvidencePolicy`.

Kanon-Disziplin: der Personal-Day-Wert eines vergangenen Tages wird hier bei jedem
Lesevorgang neu aus `Person.birth_date` + `LifeTrackingEntry.entry_date` abgeleitet.
`LifeTrackingEntry.calculation_id` ist reine Provenienz und wird dafuer nie
herangezogen -- sonst haette ein veralteter `Calculation`-Snapshot die Macht, den
Kanon zu ueberschreiben.

KEIN LLM-Import. Der Statement-Text stammt aus dem festen Template in
`evidence_analysis_service.py` und wird vor Auslieferung strukturell geprueft.
"""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from numra_api.models import CustomMetricDefinition, LifeTrackingEntry, PatternAnalysis, Person
from numra_api.models.enums import ConfidenceCategory, CorrelationTarget
from numra_api.repositories.evidence import create_pattern_analysis, get_active_evidence_policy
from numra_api.repositories.life_tracking import (
    get_custom_metric_definition_by_key,
    list_life_tracking_entries_for_person,
)
from numra_api.services.errors import (
    EvidencePolicyNotFound,
    EvidenceStatementLintFailed,
    NotFoundError,
)
from numra_api.services.evidence_analysis_service import (
    METRIC_LABELS_DE,
    STANDARD_METRIC_KEYS,
    EvidencePolicySnapshot,
    EvidenceSample,
    compute_evidence_result,
)
from numra_interpretation.report.evidence_linter import lint_structured_statement
from numra_numerology.timing.lookup import (
    compute_personal_day_for_date,
    compute_personal_month_for_date,
    compute_personal_year_for_date,
)

__all__ = ["compute_evidence_result_for_person", "save_pattern_analysis"]

#: Ein Eintrag pro `CorrelationTarget` -- die Zuordnung ist die einzige Stelle, an
#: der dieser Service ueberhaupt weiss, welches Kanon-Mass gefragt ist.
_BUCKET_LOOKUPS = {
    CorrelationTarget.PERSONAL_DAY: compute_personal_day_for_date,
    CorrelationTarget.PERSONAL_MONTH: compute_personal_month_for_date,
    CorrelationTarget.PERSONAL_YEAR: compute_personal_year_for_date,
}


async def _resolve_metric_label(db: AsyncSession, *, person_id: uuid.UUID, metric_key: str) -> str:
    """Ein unbekannter `metric_key` ist ein 404 -- weder eine der fuenf festen
    Metriken noch eine `CustomMetricDefinition` dieser Person. Auch stillgelegte
    Definitionen zaehlen: ihre historischen Werte bleiben auswertbar."""
    if metric_key in STANDARD_METRIC_KEYS:
        return METRIC_LABELS_DE[metric_key]
    definition: CustomMetricDefinition | None = await get_custom_metric_definition_by_key(
        db, person_id=person_id, metric_key=metric_key
    )
    if definition is None:
        raise NotFoundError(f"metric {metric_key!r} not found for person {person_id}")
    return definition.label


def _metric_value(entry: LifeTrackingEntry, metric_key: str) -> int | None:
    if metric_key in STANDARD_METRIC_KEYS:
        value = getattr(entry, metric_key)
        assert value is None or isinstance(value, int)
        return value
    for metric_value in entry.metric_values:
        if metric_value.metric_key == metric_key:
            return metric_value.value
    return None


def _build_samples(
    entries: list[LifeTrackingEntry],
    *,
    birth_date: dt.date,
    metric_key: str,
    correlation_target: CorrelationTarget,
) -> list[EvidenceSample]:
    lookup = _BUCKET_LOOKUPS[correlation_target]
    return [
        EvidenceSample(
            entry_date=entry.entry_date,
            bucket_value=lookup(birth_date, entry.entry_date).effective_value,
            metric_value=_metric_value(entry, metric_key),
        )
        for entry in entries
    ]


async def _load_policy_snapshot(db: AsyncSession) -> EvidencePolicySnapshot:
    policy = await get_active_evidence_policy(db)
    if policy is None:
        raise EvidencePolicyNotFound("no active EvidencePolicy")
    thresholds = {
        str(key): float(value) for key, value in policy.confidence_category_thresholds.items()
    }
    return EvidencePolicySnapshot(
        version=policy.version,
        minimum_total_sample_count=policy.minimum_total_sample_count,
        minimum_sample_count_per_bucket=policy.minimum_sample_count_per_bucket,
        minimum_observation_window_days=policy.minimum_observation_window_days,
        missing_data_handling=policy.missing_data_handling,
        outlier_policy=policy.outlier_policy,
        multiple_comparison_protection=policy.multiple_comparison_protection,
        effect_size_threshold=policy.effect_size_threshold,
        confidence_category_thresholds=thresholds,
    )


async def compute_evidence_result_for_person(
    db: AsyncSession,
    *,
    person: Person,
    metric_key: str,
    correlation_target: CorrelationTarget,
    correlation_target_value: int,
) -> dict[str, object]:
    """Berechnet ein `EvidenceResult` und gibt es als reines Mapping zurueck.

    `person` ist bereits durch das IDOR-Gate der Route gegangen (`get_person(db,
    person_id=..., user_id=user.id)`); dieser Service prueft die Eigentuemerschaft
    nicht erneut, filtert die Eintraege aber zusaetzlich auf `person.user_id`.

    `NO_RELIABLE_PATTERN` kehrt frueh zurueck und laeuft NICHT durch den
    Statement-Linter -- es gibt kein Statement zu pruefen, und ein leeres Ergebnis
    ist ausdruecklich kein Fehler."""
    policy = await _load_policy_snapshot(db)
    metric_label = await _resolve_metric_label(db, person_id=person.id, metric_key=metric_key)
    entries = await list_life_tracking_entries_for_person(
        db, person_id=person.id, user_id=person.user_id
    )
    samples = _build_samples(
        entries,
        birth_date=person.birth_date,
        metric_key=metric_key,
        correlation_target=correlation_target,
    )
    result = compute_evidence_result(
        samples=samples,
        policy=policy,
        correlation_target=correlation_target.value,
        correlation_target_value=correlation_target_value,
        metric_label=metric_label,
    )

    if result["confidence_category"] == ConfidenceCategory.NO_RELIABLE_PATTERN:
        return result

    lint = lint_structured_statement(result)
    if not lint.is_valid:
        raise EvidenceStatementLintFailed("; ".join(lint.errors))
    return result


async def save_pattern_analysis(
    db: AsyncSession,
    *,
    person: Person,
    user_id: uuid.UUID,
    metric_key: str,
    correlation_target: CorrelationTarget,
    correlation_target_value: int,
) -> PatternAnalysis:
    """Snapshot eines serverseitig NEU berechneten Ergebnisses. Der Aufrufer liefert
    nur die Frage (Metrik + Target + Wert), nie die Antwort."""
    result = await compute_evidence_result_for_person(
        db,
        person=person,
        metric_key=metric_key,
        correlation_target=correlation_target,
        correlation_target_value=correlation_target_value,
    )
    return await create_pattern_analysis(
        db,
        person_id=person.id,
        user_id=user_id,
        evidence_policy_version=result["evidence_policy_version"],
        metric_key=metric_key,
        correlation_target=correlation_target.value,
        correlation_target_value=correlation_target_value,
        result_json=result,
    )
