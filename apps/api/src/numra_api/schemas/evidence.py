from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field

from numra_api.models.enums import ConfidenceCategory, CorrelationTarget


class EvidenceResultOut(BaseModel):
    """Reines Lese-Ergebnis, kein DB-Artefakt (specs/v2/evidence-policy.md).

    `confidence_category == NO_RELIABLE_PATTERN` ist ein gueltiges, erwartetes
    Ergebnis mit HTTP 200 -- dann sind `effect_size`, `baseline_mean`, `bucket_mean`
    und `statement_text` allesamt `None`, waehrend `sample_size` und
    `observation_window_days` weiterhin gefuellt sind: der Nutzer soll sehen, wie
    weit er von einer belastbaren Aussage entfernt ist."""

    sample_size: int
    observation_window_days: int
    confidence_category: ConfidenceCategory
    effect_size: float | None
    baseline_mean: float | None
    bucket_mean: float | None
    statement_text: str | None
    evidence_policy_version: int


class PatternAnalysisCreateRequest(BaseModel):
    """Exakt die Query-Parameter von `GET .../evidence-results` -- und bewusst NICHT
    das Ergebnis: `POST .../pattern-analyses` rechnet serverseitig neu ueber
    denselben Codepfad. Ein clientgeliefertes `result_json` wuerde erlauben,
    `sample_size`/`confidence_category` frei zu erfinden."""

    metric_key: str = Field(min_length=1, max_length=60)
    correlation_target: CorrelationTarget
    correlation_target_value: int = Field(ge=0)


class PatternAnalysisOut(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    evidence_policy_version: int
    metric_key: str
    correlation_target: CorrelationTarget
    correlation_target_value: int
    result: EvidenceResultOut
    created_at: dt.datetime
