from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from numra_interpretation.composer import (
    CORE_METRIC_IDS,
    TIMING_METRIC_IDS,
    compose_extended_sections,
    compose_interpretation,
    compose_section,
    compose_timing_sections,
)
from numra_interpretation.knowledge_loader import load_knowledge_base
from numra_numerology.engine import calculate_profile
from numra_numerology.models.metric import CalculationMetric
from numra_numerology.models.person import PersonInput
from numra_numerology.models.reduction import MetricFlag
from numra_numerology.models.trace import CalculationTrace

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[4]
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"


@pytest.fixture(scope="module")
def knowledge_base():
    return load_knowledge_base(KNOWLEDGE_ROOT)


@pytest.fixture(scope="module")
def sample_profile():
    """Deliberately NOT Lukas Springer / 1986-07-18 — the phase-3 task requires
    structural assertions against a profile built through the real engine, not pasted
    golden values."""
    person = PersonInput(
        birth_first_names="Anna",
        birth_middle_names="Marie",
        birth_last_name="Berger",
        birth_date=dt.date(1990, 3, 14),
    )
    return calculate_profile(person, as_of_date=dt.date(2026, 8, 19))


def test_every_core_metric_has_a_section(sample_profile, knowledge_base) -> None:
    interpretation = compose_interpretation(sample_profile, knowledge_base)
    section_metric_ids = [section.metric_id for section in interpretation.sections]
    assert section_metric_ids == list(CORE_METRIC_IDS)
    assert len(section_metric_ids) == len(set(section_metric_ids)), "no duplicate sections"


def test_section_display_value_matches_profile(sample_profile, knowledge_base) -> None:
    interpretation = compose_interpretation(sample_profile, knowledge_base)
    for section in interpretation.sections:
        profile_metric = getattr(sample_profile.core_numbers, section.metric_id)
        assert section.display_value == profile_metric.display_value


def test_no_section_is_empty(sample_profile, knowledge_base) -> None:
    interpretation = compose_interpretation(sample_profile, knowledge_base)
    for section in interpretation.sections:
        assert section.text_de.strip() != ""
        assert section.display_name_de.strip() != ""
        assert len(section.core_themes) > 0
        assert len(section.shadows) > 0


def test_section_text_references_metric_display_name_and_value(
    sample_profile, knowledge_base
) -> None:
    interpretation = compose_interpretation(sample_profile, knowledge_base)
    for section in interpretation.sections:
        assert section.display_name_de in section.text_de
        assert section.display_value in section.text_de


def test_interpretation_carries_knowledge_version_and_profile_hash(
    sample_profile, knowledge_base
) -> None:
    interpretation = compose_interpretation(sample_profile, knowledge_base)
    assert interpretation.knowledge_version == knowledge_base.manifest.version
    assert interpretation.profile_deterministic_hash == sample_profile.deterministic_hash


def test_composing_twice_is_deterministic(sample_profile, knowledge_base) -> None:
    first = compose_interpretation(sample_profile, knowledge_base)
    second = compose_interpretation(sample_profile, knowledge_base)
    assert first == second


def _fake_metric(
    *, master_number: int | None, root_value: int, flags: tuple = ()
) -> CalculationMetric:
    effective = master_number if master_number is not None else root_value
    return CalculationMetric(
        metric_id="life_path",
        system="pythagorean",
        method="segmented_v1",
        source_value=None,
        raw_value=13,
        root_value=root_value,
        master_number=master_number,
        effective_value=effective,
        display_value="13/4" if master_number is None else f"{master_number}/{root_value}",
        calculation_trace=CalculationTrace(input_refs=(), operations=()),
        flags=flags,
    )


def test_compose_section_resolves_master_number_knowledge(knowledge_base) -> None:
    metric = _fake_metric(master_number=22, root_value=4)
    section = compose_section("life_path", metric, knowledge_base)
    assert section.number_value == 22
    assert section.is_master is True


def test_compose_section_resolves_root_number_knowledge_for_non_master(knowledge_base) -> None:
    metric = _fake_metric(master_number=None, root_value=4)
    section = compose_section("life_path", metric, knowledge_base)
    assert section.number_value == 4
    assert section.is_master is False


def test_compose_section_includes_karmic_debt_text_when_flagged(knowledge_base) -> None:
    flags = (MetricFlag(code="KARMIC_DEBT", value="13/4", source_raw_value=13),)
    metric = _fake_metric(master_number=None, root_value=4, flags=flags)
    section = compose_section("life_path", metric, knowledge_base)
    assert section.karmic_debt_compound == "13/4"
    assert "13/4" in section.text_de
    assert "Disziplin" in section.text_de  # from knowledge/karmic-debts/13-4.yaml


def test_compose_section_without_karmic_debt_flag_has_no_karmic_text(knowledge_base) -> None:
    metric = _fake_metric(master_number=None, root_value=4)
    section = compose_section("life_path", metric, knowledge_base)
    assert section.karmic_debt_compound is None


# --- V1.5 Epic J: timing + extended sections -------------------------------------

EXTENDED_METRIC_IDS = (
    "hidden_passion",
    "karmic_lessons",
    "subconscious_self",
    "cornerstone",
    "capstone",
    "first_vowel",
    "intensity_table",
    "pinnacle_1",
    "pinnacle_2",
    "pinnacle_3",
    "pinnacle_4",
    "challenge_1",
    "challenge_2",
    "challenge_3",
    "challenge_4",
)


def test_compose_timing_sections_covers_personal_year_month_day(
    sample_profile, knowledge_base
) -> None:
    sections = compose_timing_sections(sample_profile, knowledge_base)
    assert [s.metric_id for s in sections] == list(TIMING_METRIC_IDS)
    for section in sections:
        profile_metric = getattr(sample_profile.timing, section.metric_id)
        assert section.display_value == profile_metric.display_value
        assert section.text_de.strip() != ""


def test_compose_extended_sections_covers_every_extended_metric(
    sample_profile, knowledge_base
) -> None:
    sections = compose_extended_sections(sample_profile, knowledge_base)
    assert [s.metric_id for s in sections] == list(EXTENDED_METRIC_IDS)
    assert len(sections) == len(set(s.metric_id for s in sections)), "no duplicate sections"


def test_extended_sections_are_never_empty(sample_profile, knowledge_base) -> None:
    for section in compose_extended_sections(sample_profile, knowledge_base):
        assert section.text_de.strip() != ""
        assert section.display_name_de.strip() != ""


def test_extended_sections_composing_twice_is_deterministic(sample_profile, knowledge_base) -> None:
    first = compose_extended_sections(sample_profile, knowledge_base)
    second = compose_extended_sections(sample_profile, knowledge_base)
    assert first == second


def test_compose_interpretation_includes_timing_and_extended_sections(
    sample_profile, knowledge_base
) -> None:
    interpretation = compose_interpretation(sample_profile, knowledge_base)
    assert [s.metric_id for s in interpretation.timing_sections] == list(TIMING_METRIC_IDS)
    assert [s.metric_id for s in interpretation.extended_sections] == list(EXTENDED_METRIC_IDS)
    # Unchanged core-metric behavior (backward compatible with the phase-3 shape).
    assert [s.metric_id for s in interpretation.sections] == list(CORE_METRIC_IDS)


def test_hidden_passion_section_cites_the_dominant_numbers(sample_profile, knowledge_base) -> None:
    section = next(
        s
        for s in compose_extended_sections(sample_profile, knowledge_base)
        if s.metric_id == "hidden_passion"
    )
    for value in sample_profile.core_numbers.hidden_passion.values:
        assert str(value) in section.text_de
        assert f"numbers/{value}" in section.knowledge_refs


def test_pinnacle_sections_reference_the_profiles_own_reduction_results(
    sample_profile, knowledge_base
) -> None:
    sections = compose_extended_sections(sample_profile, knowledge_base)
    pinnacle_results = (
        sample_profile.cycles.pinnacles.pinnacle_1,
        sample_profile.cycles.pinnacles.pinnacle_2,
        sample_profile.cycles.pinnacles.pinnacle_3,
        sample_profile.cycles.pinnacles.pinnacle_4,
    )
    for index, result in enumerate(pinnacle_results, start=1):
        section = next(s for s in sections if s.metric_id == f"pinnacle_{index}")
        assert result.display_value in section.text_de
        assert f"numbers/{result.effective_value}" in section.knowledge_refs


def test_challenge_zero_is_composed_without_a_number_lookup(knowledge_base) -> None:
    """1990-05-05: month=5, day=5 -> challenge_1 = |5-5| = 0, which has no
    `knowledge/numbers/0.yaml` entry -- must be handled without raising KeyError."""
    person = PersonInput(
        birth_first_names="Erika",
        birth_last_name="Muster",
        birth_date=dt.date(1990, 5, 5),
    )
    profile = calculate_profile(person, as_of_date=dt.date(2026, 8, 19))
    assert profile.cycles.challenges.challenge_1 == 0

    section = next(
        s
        for s in compose_extended_sections(profile, knowledge_base)
        if s.metric_id == "challenge_1"
    )
    assert "0" in section.text_de
    assert section.knowledge_refs == ()
