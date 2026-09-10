from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from numra_interpretation.knowledge_loader import load_knowledge_base
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput
from numra_relationship_interpretation.context import (
    assemble_relationship_context,
    assemble_shadow_context,
    primary_shadow_theme,
)
from numra_relationship_interpretation.errors import ShadowInteractionRuleMissing
from numra_relationship_interpretation.knowledge_loader import (
    load_relationship_frame,
    load_shadow_interaction_rules,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[4]
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"


@pytest.fixture(scope="module")
def knowledge_base():
    return load_knowledge_base(KNOWLEDGE_ROOT)


@pytest.fixture(scope="module")
def profile_a():
    person = PersonInput(
        birth_first_names="Anna",
        birth_middle_names="Marie",
        birth_last_name="Berger",
        birth_date=dt.date(1990, 3, 14),
    )
    return calculate_profile(person, as_of_date=dt.date(2026, 8, 19))


@pytest.fixture(scope="module")
def profile_b():
    person = PersonInput(
        birth_first_names="Ben",
        birth_middle_names=None,
        birth_last_name="Fischer",
        birth_date=dt.date(1988, 7, 22),
    )
    return calculate_profile(person, as_of_date=dt.date(2026, 8, 19))


def _profile_for_birth_date(year: int, month: int, day: int):
    person = PersonInput(
        birth_first_names="Test",
        birth_middle_names=None,
        birth_last_name="Person",
        birth_date=dt.date(year, month, day),
    )
    return calculate_profile(person, as_of_date=dt.date(2026, 8, 19))


@pytest.fixture(scope="module")
def profile_lp11():
    return _profile_for_birth_date(1960, 1, 3)


@pytest.fixture(scope="module")
def profile_lp22():
    return _profile_for_birth_date(1986, 7, 18)


@pytest.fixture(scope="module")
def profile_lp33():
    return _profile_for_birth_date(1960, 4, 22)


@pytest.fixture(scope="module")
def profile_lp6():
    return _profile_for_birth_date(1979, 1, 6)


@pytest.mark.parametrize(
    "birth, expected_theme",
    [
        ((1960, 1, 3), "Überreizung"),
        ((1986, 7, 18), "enormer innerer Druck"),
        ((1960, 4, 22), "Märtyrerrolle"),
    ],
)
def test_primary_shadow_theme_for_master_life_paths(birth, expected_theme, knowledge_base) -> None:
    profile = _profile_for_birth_date(*birth)
    assert primary_shadow_theme(profile, knowledge_base) == expected_theme


def test_assemble_shadow_context_resolves_master_pair(profile_lp22, knowledge_base) -> None:
    rules = load_shadow_interaction_rules(KNOWLEDGE_ROOT)
    context = assemble_shadow_context(
        profile_a=profile_lp22,
        profile_b=profile_lp22,
        knowledge=knowledge_base,
        shadow_rules=rules,
    )
    assert context.shadow_theme_a == "enormer innerer Druck"
    assert {context.rule.shadow_theme_a, context.rule.shadow_theme_b} == {"enormer innerer Druck"}


def test_assemble_shadow_context_resolves_life_path_6_pair(profile_lp6, knowledge_base) -> None:
    """Life Path 6's primary shadow theme uses the real umlaut ('Überverantwortung');
    the rules table must match it exactly, not the old ASCII transcription
    ('Ueberverantwortung'). Same failure mode for Life Path 4 and 7."""
    rules = load_shadow_interaction_rules(KNOWLEDGE_ROOT)
    context = assemble_shadow_context(
        profile_a=profile_lp6,
        profile_b=profile_lp6,
        knowledge=knowledge_base,
        shadow_rules=rules,
    )
    assert context.shadow_theme_a == "Überverantwortung"
    assert context.rule is not None


def test_primary_shadow_theme_is_deterministic(profile_a, knowledge_base) -> None:
    theme1 = primary_shadow_theme(profile_a, knowledge_base)
    theme2 = primary_shadow_theme(profile_a, knowledge_base)
    assert theme1 == theme2
    assert isinstance(theme1, str) and theme1


def test_assemble_relationship_context_covers_all_dimensions(profile_a, profile_b) -> None:
    frame = load_relationship_frame(KNOWLEDGE_ROOT, "PARTNER")
    assert frame is not None
    context = assemble_relationship_context(profile_a=profile_a, profile_b=profile_b, frame=frame)
    assert set(context.dimension_blocks) == set(frame.dimensions)
    for blocks in context.dimension_blocks.values():
        assert len(blocks) >= 1
        assert blocks[0].role == "knowledge"
    assert context.profile_a_blocks
    assert context.profile_b_blocks
    assert "a:life_path" in context.valid_metric_ids
    assert "b:life_path" in context.valid_metric_ids


def test_assemble_shadow_context_resolves_a_rule(profile_a, profile_b, knowledge_base) -> None:
    rules = load_shadow_interaction_rules(KNOWLEDGE_ROOT)
    context = assemble_shadow_context(
        profile_a=profile_a, profile_b=profile_b, knowledge=knowledge_base, shadow_rules=rules
    )
    assert context.rule is not None
    assert {context.rule.shadow_theme_a, context.rule.shadow_theme_b} == {
        context.shadow_theme_a,
        context.shadow_theme_b,
    }


def test_assemble_shadow_context_missing_rule_raises(profile_a, profile_b, knowledge_base) -> None:
    with pytest.raises(ShadowInteractionRuleMissing):
        assemble_shadow_context(
            profile_a=profile_a, profile_b=profile_b, knowledge=knowledge_base, shadow_rules=()
        )
