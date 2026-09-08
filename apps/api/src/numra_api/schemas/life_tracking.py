from __future__ import annotations

import datetime as dt
import uuid

from pydantic import BaseModel, Field, ValidationInfo, field_validator

from numra_api.services.evidence_analysis_service import STANDARD_METRIC_KEYS

#: Die Standard-Skala aller fuenf festen Metriken. Als Konstante hier, weil die
#: gleiche Grenze zusaetzlich als CHECK-Constraint auf `life_tracking_entries`
#: liegt -- die API lehnt frueh ab, die Datenbank ist die letzte Instanz.
SCALE_MIN = 1
SCALE_MAX = 10


class LifeTrackingEntryCreateRequest(BaseModel):
    entry_date: dt.date
    calculation_id: uuid.UUID | None = None
    mood: int | None = Field(default=None, ge=SCALE_MIN, le=SCALE_MAX)
    energy: int | None = Field(default=None, ge=SCALE_MIN, le=SCALE_MAX)
    sleep: int | None = Field(default=None, ge=SCALE_MIN, le=SCALE_MAX)
    stress: int | None = Field(default=None, ge=SCALE_MIN, le=SCALE_MAX)
    focus: int | None = Field(default=None, ge=SCALE_MIN, le=SCALE_MAX)
    note: str | None = None
    #: Nur Custom-Metriken. Ein Standard-Key hier ist ein Fehler, kein Alias auf die
    #: gleichnamige Spalte -- sonst gaebe es zwei Wege, denselben Wert zu setzen.
    custom_metrics: dict[str, int] = Field(default_factory=dict)

    @field_validator("custom_metrics")
    @classmethod
    def _reject_standard_keys(cls, value: dict[str, int]) -> dict[str, int]:
        collisions = sorted(set(value) & set(STANDARD_METRIC_KEYS))
        if collisions:
            raise ValueError(f"custom_metrics must not contain standard metric keys: {collisions}")
        return value


class LifeTrackingEntryPatchRequest(BaseModel):
    """Jedes Feld optional; die Route wertet `model_fields_set` aus, sodass nur
    tatsaechlich gesendete Felder angewendet werden -- gleiches Muster wie
    `PrivateReflectionPatchRequest`. `custom_metrics` ersetzt beim Senden die
    gesamte Custom-Wertmenge des Eintrags (kein partielles Merge)."""

    entry_date: dt.date | None = None
    calculation_id: uuid.UUID | None = None
    mood: int | None = Field(default=None, ge=SCALE_MIN, le=SCALE_MAX)
    energy: int | None = Field(default=None, ge=SCALE_MIN, le=SCALE_MAX)
    sleep: int | None = Field(default=None, ge=SCALE_MIN, le=SCALE_MAX)
    stress: int | None = Field(default=None, ge=SCALE_MIN, le=SCALE_MAX)
    focus: int | None = Field(default=None, ge=SCALE_MIN, le=SCALE_MAX)
    note: str | None = None
    custom_metrics: dict[str, int] | None = None


class LifeTrackingEntryOut(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    entry_date: dt.date
    calculation_id: uuid.UUID | None
    mood: int | None
    energy: int | None
    sleep: int | None
    stress: int | None
    focus: int | None
    note: str | None
    custom_metrics: dict[str, int]
    created_at: dt.datetime
    updated_at: dt.datetime


class CustomMetricDefinitionCreateRequest(BaseModel):
    metric_key: str = Field(min_length=1, max_length=60, pattern=r"^[a-z][a-z0-9_]*$")
    label: str = Field(min_length=1, max_length=120)
    scale_min: int = SCALE_MIN
    scale_max: int = SCALE_MAX

    @field_validator("scale_max")
    @classmethod
    def _reject_inverted_scale(cls, value: int, info: ValidationInfo) -> int:
        scale_min = info.data.get("scale_min")
        if scale_min is not None and value <= scale_min:
            raise ValueError("scale_max must be greater than scale_min")
        return value


class CustomMetricDefinitionPatchRequest(BaseModel):
    """`metric_key` fehlt hier bewusst: er ist unveraenderlich (siehe
    `services.errors.MetricKeyImmutable`). Stilllegen und einen neuen Key anlegen
    ist der einzige Weg, eine Metrik semantisch zu aendern."""

    label: str | None = Field(default=None, min_length=1, max_length=120)
    active: bool | None = None


class CustomMetricDefinitionOut(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    metric_key: str
    label: str
    scale_min: int
    scale_max: int
    active: bool
    created_at: dt.datetime
    retired_at: dt.datetime | None

    model_config = {"from_attributes": True}
