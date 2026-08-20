from __future__ import annotations

import datetime as dt

from numra_numerology.cycles.challenges import compute_challenges
from numra_numerology.cycles.period_cycles import compute_period_cycles
from numra_numerology.cycles.pinnacles import build_pinnacles_model, compute_pinnacle_diagnostics
from numra_numerology.cycles.segments import compute_birth_segments
from numra_numerology.hashing import compute_deterministic_hash
from numra_numerology.metrics.date_metrics import (
    compute_attitude,
    compute_birthday,
    compute_life_path,
    compute_life_path_direct_diagnostic,
    compute_maturity,
    diagnostic_payload,
)
from numra_numerology.metrics.intensity import build_intensity_table
from numra_numerology.metrics.name_metrics import (
    compute_balance,
    compute_capstone,
    compute_cornerstone,
    compute_expression,
    compute_first_vowel,
    compute_hidden_passion,
    compute_karmic_lessons,
    compute_personality,
    compute_soul_urge,
    compute_subconscious_self,
)
from numra_numerology.models.cycles import Cycles
from numra_numerology.models.person import PersonInput
from numra_numerology.models.profile import (
    CanonicalProfile,
    CoreNumbers,
    Diagnostics,
    PersonSummary,
)
from numra_numerology.models.timing import Timing
from numra_numerology.normalization.pipeline import normalize_name
from numra_numerology.timing.personal import (
    compute_personal_day,
    compute_personal_month,
    compute_personal_year,
    compute_universal_year,
)

__all__ = ["calculate_profile"]


def calculate_profile(person: PersonInput, as_of_date: dt.date) -> CanonicalProfile:
    """Compute the full NUMRA Canonical Profile for a person as of a given date.

    This function never calls ``date.today()`` and never rejects a future birth date —
    that application-layer rule (``FUTURE_BIRTH_DATE_NOT_ALLOWED``) lives outside this
    package (canon-spec.md §30). It is pure: same ``person`` + ``as_of_date`` always
    produces the same result, including ``deterministic_hash``.
    """
    normalization = normalize_name(person.full_birth_name)
    calculation_string = normalization.calculation_string
    components = normalization.components

    segments = compute_birth_segments(person.birth_date)

    life_path = compute_life_path(segments)
    birthday = compute_birthday(person.birth_date)
    attitude = compute_attitude(person.birth_date)
    expression = compute_expression(calculation_string, components)
    soul_urge = compute_soul_urge(calculation_string)
    personality = compute_personality(calculation_string)
    maturity = compute_maturity(life_path.root_value, expression.root_value)
    balance = compute_balance(components)

    intensity_table = build_intensity_table(calculation_string)
    hidden_passion = compute_hidden_passion(calculation_string, intensity_table)
    karmic_lessons = compute_karmic_lessons(calculation_string, intensity_table)
    subconscious_self = compute_subconscious_self(calculation_string, intensity_table)

    core_numbers = CoreNumbers(
        life_path=life_path,
        birthday=birthday,
        attitude=attitude,
        expression=expression,
        soul_urge=soul_urge,
        personality=personality,
        maturity=maturity,
        balance=balance,
        hidden_passion=hidden_passion,
        karmic_lessons=karmic_lessons,
        subconscious_self=subconscious_self,
        cornerstone=compute_cornerstone(calculation_string),
        capstone=compute_capstone(calculation_string),
        first_vowel=compute_first_vowel(calculation_string),
        intensity_table=intensity_table,
    )

    pinnacles = build_pinnacles_model(segments, person.birth_date, life_path.root_value)
    challenges = compute_challenges(segments)
    period_cycles = compute_period_cycles(segments)
    cycles = Cycles(period_cycles=period_cycles, pinnacles=pinnacles, challenges=challenges)

    universal_year = compute_universal_year(as_of_date.year)
    personal_year = compute_personal_year(segments, universal_year)
    personal_month = compute_personal_month(personal_year, as_of_date.month)
    personal_day = compute_personal_day(personal_month, as_of_date.day)
    timing = Timing(
        as_of_date=as_of_date,
        universal_year=universal_year,
        personal_year=personal_year,
        personal_month=personal_month,
        personal_day=personal_day,
    )

    life_path_diagnostic = compute_life_path_direct_diagnostic(person.birth_date)
    pinnacle_diagnostics = compute_pinnacle_diagnostics(
        person.birth_date, year_compound=segments.year.raw_value
    )
    diagnostics = Diagnostics(
        life_path={
            "alternative_methods": {
                "direct_digit_sum": diagnostic_payload(life_path_diagnostic),
            }
        },
        pinnacles={
            "alternative_methods": {
                "pinnacle_1_historical": pinnacle_diagnostics.pinnacle_1_historical,
                "pinnacle_2_historical": pinnacle_diagnostics.pinnacle_2_historical,
            }
        },
    )

    person_summary = PersonSummary(
        birth_first_names=person.birth_first_names,
        birth_middle_names=person.birth_middle_names,
        birth_last_name=person.birth_last_name,
        birth_date=person.birth_date.isoformat(),
        birth_time=person.birth_time,
        birth_place=person.birth_place,
    )

    draft = CanonicalProfile(
        deterministic_hash=None,
        person=person_summary,
        normalization=normalization,
        core_numbers=core_numbers,
        cycles=cycles,
        timing=timing,
        diagnostics=diagnostics,
        warnings=(),
    )
    digest = compute_deterministic_hash(draft)
    return draft.model_copy(update={"deterministic_hash": digest})
