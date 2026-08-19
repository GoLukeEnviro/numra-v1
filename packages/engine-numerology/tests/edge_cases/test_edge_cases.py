from __future__ import annotations

import datetime as dt

import pytest

from numra_numerology.cycles.pinnacles import _add_years
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput
from numra_numerology.reduction.core import reduce_compound

pytestmark = pytest.mark.unit


def _profile(first: str, last: str, birth: dt.date, as_of: dt.date | None = None):
    person = PersonInput(birth_first_names=first, birth_last_name=last, birth_date=birth)
    return calculate_profile(person, as_of_date=as_of or dt.date(2026, 1, 1))


def test_birthday_master_11() -> None:
    profile = _profile("Test", "Person", dt.date(1990, 5, 11))
    assert profile.core_numbers.birthday.display_value == "11/2"
    assert profile.core_numbers.birthday.master_number == 11


def test_birthday_master_22() -> None:
    profile = _profile("Test", "Person", dt.date(1990, 5, 22))
    assert profile.core_numbers.birthday.display_value == "22/4"
    assert profile.core_numbers.birthday.master_number == 22


def test_44_compound_not_master() -> None:
    result = reduce_compound(44)
    assert result.master_number is None
    assert result.display_value == "44/8"


def test_55_compound_not_master() -> None:
    result = reduce_compound(55)
    assert result.master_number is None
    assert result.display_value == "55/1"


def test_leap_day_birth_computes_without_error() -> None:
    profile = _profile("Anna", "Beispiel", dt.date(1988, 2, 29))
    assert profile.core_numbers.life_path is not None


def test_leap_day_anniversary_non_leap_year_rolls_to_feb_28() -> None:
    assert _add_years(dt.date(1988, 2, 29), 1) == dt.date(1989, 2, 28)


def test_leap_day_anniversary_leap_year_keeps_feb_29() -> None:
    assert _add_years(dt.date(1988, 2, 29), 4) == dt.date(1992, 2, 29)


def test_multiple_first_names_components() -> None:
    profile = _profile("Anna Maria", "Muster", dt.date(1990, 1, 1))
    assert profile.normalization.components == ("ANNA", "MARIA", "MUSTER")


def test_hyphenated_name_multiple_components_via_engine() -> None:
    person = PersonInput(
        birth_first_names="Anna-Maria",
        birth_middle_names="von",
        birth_last_name="Beispiel",
        birth_date=dt.date(1990, 1, 1),
    )
    profile = calculate_profile(person, as_of_date=dt.date(2026, 1, 1))
    assert profile.normalization.components == ("ANNA", "MARIA", "VON", "BEISPIEL")


def test_apostrophe_name_via_engine() -> None:
    profile = _profile("Sean", "O'Brien", dt.date(1990, 1, 1))
    assert profile.normalization.components == ("SEAN", "O", "BRIEN")


def test_german_diacritics_full_profile_computes() -> None:
    profile = _profile("Jürgen", "Müller", dt.date(1990, 1, 1))
    assert profile.normalization.calculation_string == "JURGENMULLER"
    assert profile.core_numbers.expression.raw_value > 0


def test_latin_diacritics_e_and_n() -> None:
    profile = _profile("Éowyn", "Núñez", dt.date(1990, 1, 1))
    assert profile.normalization.calculation_string == "EOWYNNUNEZ"


def test_no_vowels_name_flags_and_invariant() -> None:
    profile = _profile("Xzc", "Trprst", dt.date(1990, 1, 1))
    core = profile.core_numbers
    assert core.soul_urge.raw_value == 0
    assert core.soul_urge.display_value == "0"
    assert any(flag.code == "NO_VOWELS" for flag in core.soul_urge.flags)
    assert core.first_vowel.letter is None
    assert core.expression.raw_value == core.soul_urge.raw_value + core.personality.raw_value


def test_hidden_passion_tie() -> None:
    profile = _profile("Lukas", "Springer", dt.date(1986, 7, 18))
    hp = profile.core_numbers.hidden_passion
    assert len(hp.values) > 1


def test_hidden_passion_unique_max() -> None:
    profile = _profile("Aaaa", "B", dt.date(1990, 1, 1))
    hp = profile.core_numbers.hidden_passion
    assert list(hp.values) == [1]
    assert hp.frequency == 4


def test_no_karmic_lessons_when_all_values_present() -> None:
    profile = _profile("Abcdefghi", "J", dt.date(1990, 1, 1))
    core = profile.core_numbers
    assert list(core.karmic_lessons.values) == []
    assert core.subconscious_self.value == 9


def test_multiple_karmic_lessons() -> None:
    profile = _profile("Lukas", "Springer", dt.date(1986, 7, 18))
    assert list(profile.core_numbers.karmic_lessons.values) == [4, 6, 8]


def test_challenge_can_be_zero() -> None:
    # month=5 (root 5), day=14 -> 1+4=5 (root 5) => challenge_1 = |5-5| = 0
    profile = _profile("Test", "Person", dt.date(1990, 5, 14))
    assert profile.cycles.challenges.challenge_1 == 0
