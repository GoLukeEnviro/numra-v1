"""PR-V2-11 -- lightweight Personal Day lookup for historical dates.

Used by ``numra_api.services.evidence_service`` to determine, for an arbitrary
past ``LifeTrackingEntry.entry_date``, which Personal Day the canon assigns to
that date -- without recomputing (or persisting) a second source of truth
(specs/v2/evidence-policy.md: "never stores a new Personal Day/Month/Year
value... always derived from the canon at read time").

``compute_personal_day_for_date`` reuses the exact same building blocks as
``numra_numerology.engine.calculate_profile`` (``compute_birth_segments``,
``compute_universal_year``, ``compute_personal_year``, ``compute_personal_month``,
``compute_personal_day``) -- identical code path, so the result is provably equal
to ``calculate_profile(person, as_of_date=target_date).timing.personal_day`` for
the same inputs (see tests/unit/test_timing_lookup.py). Unlike
``calculate_profile`` this module never runs name normalization -- unnecessary
overhead for a pure timing lookup that only needs ``birth_date``.

Pure Python. No network, no database, no LLM import, no global mutable state, no
randomness -- same product invariant as the rest of this package
(see ``numra_numerology/__init__.py``)."""

from __future__ import annotations

import datetime as dt

from numra_numerology.cycles.segments import compute_birth_segments
from numra_numerology.models.metric import CalculationMetric
from numra_numerology.timing.personal import (
    compute_personal_day,
    compute_personal_month,
    compute_personal_year,
    compute_universal_year,
)

__all__ = [
    "compute_personal_day_for_date",
    "compute_personal_month_for_date",
    "compute_personal_year_for_date",
]


def _timing_chain(
    birth_date: dt.date, target_date: dt.date
) -> tuple[CalculationMetric, CalculationMetric, CalculationMetric]:
    """``(personal_year, personal_month, personal_day)`` in genau der Reihenfolge und
    mit genau den Bausteinen, die ``engine.calculate_profile`` verwendet -- eine
    einzige Kette, damit die drei oeffentlichen Lookups nicht auseinanderlaufen
    koennen."""
    segments = compute_birth_segments(birth_date)
    universal_year = compute_universal_year(target_date.year)
    personal_year = compute_personal_year(segments, universal_year)
    personal_month = compute_personal_month(personal_year, target_date.month)
    personal_day = compute_personal_day(personal_month, target_date.day)
    return personal_year, personal_month, personal_day


def compute_personal_day_for_date(birth_date: dt.date, target_date: dt.date) -> CalculationMetric:
    """Personal Day metric for ``birth_date`` as of ``target_date``.

    Never calls ``date.today()`` -- ``target_date`` is always explicit, same
    discipline as ``timing/personal.py`` and ``engine.calculate_profile``."""
    return _timing_chain(birth_date, target_date)[2]


def compute_personal_month_for_date(birth_date: dt.date, target_date: dt.date) -> CalculationMetric:
    """Personal Month metric for ``birth_date`` as of ``target_date`` -- gleiche
    Kanon-Kette wie ``compute_personal_day_for_date``."""
    return _timing_chain(birth_date, target_date)[1]


def compute_personal_year_for_date(birth_date: dt.date, target_date: dt.date) -> CalculationMetric:
    """Personal Year metric for ``birth_date`` as of ``target_date`` -- gleiche
    Kanon-Kette wie ``compute_personal_day_for_date``."""
    return _timing_chain(birth_date, target_date)[0]
