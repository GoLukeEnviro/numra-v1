from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from numra_numerology.models.reduction import MetricFlag
from numra_numerology.models.trace import CalculationTrace


class CalculationMetric(BaseModel):
    """A single canonical, fully-traceable numerology metric."""

    model_config = ConfigDict(frozen=True)

    metric_id: str
    system: str
    method: str

    source_value: int | str | None
    raw_value: int
    root_value: int
    master_number: int | None
    effective_value: int
    display_value: str

    calculation_trace: CalculationTrace
    flags: tuple[MetricFlag, ...] = ()


class LetterResult(BaseModel):
    """Cornerstone / Capstone / First Vowel."""

    model_config = ConfigDict(frozen=True)

    letter: str | None
    value: int | None


class HiddenPassion(BaseModel):
    model_config = ConfigDict(frozen=True)

    values: tuple[int, ...]
    frequency: int
    calculation_trace: CalculationTrace


class KarmicLessons(BaseModel):
    model_config = ConfigDict(frozen=True)

    values: tuple[int, ...]
    calculation_trace: CalculationTrace


class SubconsciousSelf(BaseModel):
    model_config = ConfigDict(frozen=True)

    value: int
    calculation_trace: CalculationTrace


IntensityTable = dict[str, int]
