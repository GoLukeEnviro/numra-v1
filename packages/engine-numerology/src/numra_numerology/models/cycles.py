from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict

from numra_numerology.models.reduction import ReductionResult


class PeriodCycles(BaseModel):
    model_config = ConfigDict(frozen=True)

    period_1: ReductionResult
    period_2: ReductionResult
    period_3: ReductionResult


class PinnacleWindow(BaseModel):
    """Concrete calendar age window for a Pinnacle, per canon-spec.md §Pinnacle
    Altersgrenzen. Never floating-point ages; leap-day births anniversary to Feb 28 in
    non-leap years."""

    model_config = ConfigDict(frozen=True)

    start_date: dt.date | None
    end_date: dt.date | None
    start_age: int
    end_age: int | None


class Pinnacles(BaseModel):
    model_config = ConfigDict(frozen=True)

    pinnacle_1: ReductionResult
    pinnacle_2: ReductionResult
    pinnacle_3: ReductionResult
    pinnacle_4: ReductionResult
    windows: tuple[PinnacleWindow, PinnacleWindow, PinnacleWindow, PinnacleWindow]


class Challenges(BaseModel):
    model_config = ConfigDict(frozen=True)

    challenge_1: int
    challenge_2: int
    challenge_3: int
    challenge_4: int


class Cycles(BaseModel):
    model_config = ConfigDict(frozen=True)

    period_cycles: PeriodCycles
    pinnacles: Pinnacles
    challenges: Challenges
