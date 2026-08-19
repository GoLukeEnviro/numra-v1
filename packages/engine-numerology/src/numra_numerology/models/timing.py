from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict

from numra_numerology.models.metric import CalculationMetric
from numra_numerology.models.reduction import ReductionResult


class Timing(BaseModel):
    model_config = ConfigDict(frozen=True)

    as_of_date: dt.date
    universal_year: ReductionResult
    personal_year: CalculationMetric
    personal_month: CalculationMetric
    personal_day: CalculationMetric
