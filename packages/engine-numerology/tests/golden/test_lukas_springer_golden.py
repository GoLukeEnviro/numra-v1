from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import BirthPlace, BirthTime, PersonInput

pytestmark = pytest.mark.golden

FIXTURE_PATH = (
    Path(__file__).resolve().parents[4] / "fixtures" / "canonical" / "lukas-springer.v1.json"
)


@pytest.fixture(scope="module")
def golden_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


@pytest.fixture(scope="module")
def lukas_profile():
    person = PersonInput(
        birth_first_names="Lukas",
        birth_last_name="Springer",
        birth_date=dt.date(1986, 7, 18),
        birth_time=BirthTime(value=dt.time(6, 0, 0), precision="exact"),
        birth_place=BirthPlace(display_name="Meerbusch", country_code="DE"),
    )
    return calculate_profile(person, as_of_date=dt.date(2026, 8, 19))


def test_normalization(lukas_profile) -> None:
    assert lukas_profile.normalization.components == ("LUKAS", "SPRINGER")
    assert lukas_profile.normalization.calculation_string == "LUKASSPRINGER"


def test_life_path(lukas_profile, golden_fixture) -> None:
    lp = lukas_profile.core_numbers.life_path
    expected = golden_fixture["core_numbers"]["life_path"]
    assert lp.display_value == "22/4" == expected["display_value"]
    assert lp.raw_value == 22 == expected["raw_value"]
    assert lp.master_number == 22 == expected["master_number"]
    assert lp.root_value == 4 == expected["root_value"]
    assert list(lp.calculation_trace.operations[-2]["operands"]) == [9, 7, 6]


def test_life_path_direct_diagnostic(lukas_profile) -> None:
    diag = lukas_profile.diagnostics.life_path["alternative_methods"]["direct_digit_sum"]
    assert diag["raw_value"] == 40
    assert diag["display_value"] == "40/4"


def test_birthday(lukas_profile, golden_fixture) -> None:
    assert lukas_profile.core_numbers.birthday.display_value == "18/9"


def test_attitude(lukas_profile) -> None:
    assert lukas_profile.core_numbers.attitude.display_value == "25/7"


def test_expression(lukas_profile) -> None:
    expr = lukas_profile.core_numbers.expression
    assert expr.raw_value == 62
    assert expr.display_value == "62/8"
    values = expr.calculation_trace.operations[0]["values"]
    assert sum(values[:5]) == 10  # LUKAS
    assert sum(values[5:]) == 52  # SPRINGER


def test_soul_urge(lukas_profile) -> None:
    su = lukas_profile.core_numbers.soul_urge
    assert su.raw_value == 18
    assert su.display_value == "18/9"


def test_personality(lukas_profile) -> None:
    p = lukas_profile.core_numbers.personality
    assert p.raw_value == 44
    assert p.display_value == "44/8"


def test_expression_invariant(lukas_profile) -> None:
    core = lukas_profile.core_numbers
    assert core.expression.raw_value == core.soul_urge.raw_value + core.personality.raw_value


def test_maturity(lukas_profile) -> None:
    assert lukas_profile.core_numbers.maturity.display_value == "12/3"


def test_balance(lukas_profile) -> None:
    assert lukas_profile.core_numbers.balance.display_value == "4"


def test_hidden_passion(lukas_profile) -> None:
    hp = lukas_profile.core_numbers.hidden_passion
    assert list(hp.values) == [1, 9]
    assert hp.frequency == 3


def test_karmic_lessons(lukas_profile) -> None:
    assert list(lukas_profile.core_numbers.karmic_lessons.values) == [4, 6, 8]


def test_subconscious_self(lukas_profile) -> None:
    core = lukas_profile.core_numbers
    assert core.subconscious_self.value == 6
    assert core.subconscious_self.value + len(core.karmic_lessons.values) == 9


def test_intensity_table(lukas_profile) -> None:
    assert lukas_profile.core_numbers.intensity_table == {
        "1": 3,
        "2": 1,
        "3": 2,
        "4": 0,
        "5": 2,
        "6": 0,
        "7": 2,
        "8": 0,
        "9": 3,
    }


def test_cornerstone_capstone_first_vowel(lukas_profile) -> None:
    core = lukas_profile.core_numbers
    assert core.cornerstone.letter == "L"
    assert core.capstone.letter == "R"
    assert core.first_vowel.letter == "U"


def test_pinnacles(lukas_profile) -> None:
    p = lukas_profile.cycles.pinnacles
    assert p.pinnacle_1.display_value == "16/7"
    assert p.pinnacle_2.display_value == "15/6"
    assert p.pinnacle_3.display_value == "13/4"
    assert p.pinnacle_4.display_value == "13/4"


def test_pinnacle_windows_first_end_age(lukas_profile) -> None:
    windows = lukas_profile.cycles.pinnacles.windows
    assert windows[0].start_age == 0
    assert windows[0].end_age == 32  # 36 - life_path.root_value(4)
    assert windows[1].start_age == 33
    assert windows[3].end_age is None


def test_challenges(lukas_profile) -> None:
    c = lukas_profile.cycles.challenges
    assert (c.challenge_1, c.challenge_2, c.challenge_3, c.challenge_4) == (2, 3, 1, 1)


def test_personal_year_2026(lukas_profile) -> None:
    assert lukas_profile.timing.personal_year.display_value == "17/8"


def test_no_karmic_debt_flag_on_pinnacle_13_4() -> None:
    """Pinnacle 3/4 both display 13/4 but must NOT carry an automatic Core Karmic Debt
    flag — only life_path/birthday/expression/soul_urge/personality are eligible."""
    person = PersonInput(
        birth_first_names="Lukas", birth_last_name="Springer", birth_date=dt.date(1986, 7, 18)
    )
    profile = calculate_profile(person, as_of_date=dt.date(2026, 1, 1))
    assert profile.cycles.pinnacles.pinnacle_3.display_value == "13/4"


def test_deterministic_hash_stable_across_runs() -> None:
    person = PersonInput(
        birth_first_names="Lukas", birth_last_name="Springer", birth_date=dt.date(1986, 7, 18)
    )
    p1 = calculate_profile(person, as_of_date=dt.date(2026, 8, 19))
    p2 = calculate_profile(person, as_of_date=dt.date(2026, 8, 19))
    assert p1.deterministic_hash == p2.deterministic_hash
    assert p1.to_canonical_json() == p2.to_canonical_json()
