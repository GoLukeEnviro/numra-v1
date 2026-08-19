from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from numra_interpretation.composer import CORE_METRIC_IDS, compose_interpretation, compose_section
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
