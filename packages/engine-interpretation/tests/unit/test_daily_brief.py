from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from numra_interpretation.composer import TIMING_METRIC_IDS
from numra_interpretation.daily_brief import compose_daily_brief
from numra_interpretation.knowledge_loader import load_knowledge_base
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[4]
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"

# Phrases that would cross the line from reflective/symbolic language into a
# guaranteed-outcome claim -- V1.5 hard failure condition ("no predictive certainty
# language"). Checked case-insensitively against every composed sentence.
_FORBIDDEN_PREDICTIVE_PHRASES = (
    "wird passieren",
    "garantiert",
    "sicher eintreten",
    "wird definitiv",
)


@pytest.fixture(scope="module")
def knowledge_base():
    return load_knowledge_base(KNOWLEDGE_ROOT)


@pytest.fixture(scope="module")
def sample_profile():
    person = PersonInput(
        birth_first_names="Anna",
        birth_middle_names="Marie",
        birth_last_name="Berger",
        birth_date=dt.date(1990, 3, 14),
    )
    return calculate_profile(person, as_of_date=dt.date(2026, 8, 22))


def test_daily_brief_covers_personal_day_month_year(sample_profile, knowledge_base) -> None:
    brief = compose_daily_brief(sample_profile, knowledge_base)
    assert [s.metric_id for s in brief.sections] == list(TIMING_METRIC_IDS)


def test_daily_brief_uses_the_profiles_own_as_of_date(sample_profile, knowledge_base) -> None:
    brief = compose_daily_brief(sample_profile, knowledge_base)
    assert brief.as_of_date == sample_profile.timing.as_of_date == dt.date(2026, 8, 22)


def test_daily_brief_carries_the_knowledge_version(sample_profile, knowledge_base) -> None:
    brief = compose_daily_brief(sample_profile, knowledge_base)
    assert brief.knowledge_version == knowledge_base.manifest.version


def test_daily_brief_is_deterministic_for_the_same_profile(sample_profile, knowledge_base) -> None:
    first = compose_daily_brief(sample_profile, knowledge_base)
    second = compose_daily_brief(sample_profile, knowledge_base)
    assert first == second


def test_daily_brief_differs_for_a_different_as_of_date(sample_profile, knowledge_base) -> None:
    person = PersonInput(
        birth_first_names="Anna",
        birth_middle_names="Marie",
        birth_last_name="Berger",
        birth_date=dt.date(1990, 3, 14),
    )
    other_day_profile = calculate_profile(person, as_of_date=dt.date(2026, 8, 23))
    brief_today = compose_daily_brief(sample_profile, knowledge_base)
    brief_other_day = compose_daily_brief(other_day_profile, knowledge_base)
    assert brief_today.as_of_date != brief_other_day.as_of_date


def test_daily_brief_text_avoids_predictive_certainty_language(
    sample_profile, knowledge_base
) -> None:
    brief = compose_daily_brief(sample_profile, knowledge_base)
    for section in brief.sections:
        lowered = section.text_de.lower()
        for phrase in _FORBIDDEN_PREDICTIVE_PHRASES:
            assert phrase not in lowered, f"{phrase!r} found in {section.metric_id} text"
