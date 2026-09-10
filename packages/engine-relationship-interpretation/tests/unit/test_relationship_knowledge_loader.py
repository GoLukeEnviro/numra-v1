from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from numra_interpretation.knowledge_loader import load_knowledge_base
from numra_relationship_interpretation.errors import RelationshipKnowledgeLoadError
from numra_relationship_interpretation.knowledge_loader import (
    load_relationship_frame,
    load_relationship_frames_manifest,
    load_shadow_interaction_manifest,
    load_shadow_interaction_rules,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[4]
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"


def test_load_relationship_frames_manifest() -> None:
    manifest = load_relationship_frames_manifest(KNOWLEDGE_ROOT)
    assert manifest.knowledge_system == "numra-relationship-frames"
    assert manifest.language == "de"


def test_load_partner_frame() -> None:
    frame = load_relationship_frame(KNOWLEDGE_ROOT, "PARTNER")
    assert frame is not None
    assert frame.relationship_type == "PARTNER"
    expected_dimensions = {
        "communication",
        "closeness",
        "autonomy",
        "needs",
        "strengths",
        "conflict_dynamics",
    }
    assert set(frame.dimensions) == expected_dimensions
    for dimension in frame.dimensions.values():
        assert dimension.semantic_context_de.strip()
        for life_path in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "11", "22", "33"):
            assert life_path in dimension.number_modifiers


def test_load_friendship_frame() -> None:
    frame = load_relationship_frame(KNOWLEDGE_ROOT, "FRIENDSHIP")
    assert frame is not None
    assert frame.relationship_type == "FRIENDSHIP"


ALL_RELATIONSHIP_TYPES = (
    "PARTNER",
    "DATING",
    "FRIENDSHIP",
    "FAMILY",
    "SIBLINGS",
    "PARENT_CHILD",
    "WORK",
    "OTHER",
)


@pytest.mark.parametrize("relationship_type", ALL_RELATIONSHIP_TYPES)
def test_load_relationship_frame_covers_all_relationship_types(relationship_type: str) -> None:
    """specs/v2/relationship-type-spec.md defines 8 RelationshipType values -- every
    one of them must resolve to a valid, non-None frame (closes the 409
    KnowledgeFrameNotAvailable gap for DATING/FAMILY/SIBLINGS/PARENT_CHILD/WORK/OTHER)."""
    frame = load_relationship_frame(KNOWLEDGE_ROOT, relationship_type)
    assert frame is not None
    assert frame.relationship_type == relationship_type
    assert frame.dimensions
    for dimension in frame.dimensions.values():
        assert dimension.semantic_context_de.strip()
        for life_path in ("1", "2", "3", "4", "5", "6", "7", "8", "9", "11", "22", "33"):
            assert life_path in dimension.number_modifiers
            assert dimension.number_modifiers[life_path].strip()


def test_load_unknown_relationship_type_returns_none() -> None:
    """A relationship type with no matching frame file returns None -- expected, not
    an error. All 8 spec'd RelationshipType values now have frames (see
    test_load_relationship_frame_covers_all_relationship_types), so this exercises a
    type outside the enum instead."""
    assert load_relationship_frame(KNOWLEDGE_ROOT, "NOT_A_REAL_TYPE") is None


def test_load_shadow_interaction_manifest() -> None:
    manifest = load_shadow_interaction_manifest(KNOWLEDGE_ROOT)
    assert manifest.knowledge_system == "numra-shadow-interaction"


def test_load_shadow_interaction_rules_covers_all_life_path_pairs() -> None:
    rules = load_shadow_interaction_rules(KNOWLEDGE_ROOT)
    # C(12,2) + 12 diagonal (same-theme) cases over Life Path {1-9, 11, 22, 33} = 78.
    assert len(rules) == 78
    pairs = {frozenset((rule.shadow_theme_a, rule.shadow_theme_b)) for rule in rules}
    assert len(pairs) == 78
    assert len({rule.interaction_pattern_template_id for rule in rules}) == 78
    for rule in rules:
        assert rule.interaction_pattern_template_id
        assert rule.escalation_loop_template.strip()
        assert rule.deescalation_template.strip()


SUPPORTED_LIFE_PATHS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 22, 33)


def test_shadow_interaction_rules_cover_all_supported_life_path_pairs() -> None:
    """The central regression guard: every unordered pair (same number included) of
    the primary shadow themes (`shadows[0]`) for Life Path {1-9, 11, 22, 33} -- read
    from the real `knowledge/numbers` + `knowledge/master-numbers` files -- must
    resolve to exactly one rule. Catches both the ASCII/umlaut theme-key mismatch
    (Life Path 4/6/7) and the missing master-number coverage (11/22/33)."""
    knowledge = load_knowledge_base(KNOWLEDGE_ROOT)
    themes = {lp: knowledge.number(lp).shadows[0] for lp in SUPPORTED_LIFE_PATHS}
    rules = load_shadow_interaction_rules(KNOWLEDGE_ROOT)

    expected_pairs = {
        frozenset((themes[x], themes[y]))
        for x, y in itertools.combinations_with_replacement(SUPPORTED_LIFE_PATHS, 2)
    }
    assert len(expected_pairs) == 78

    for pair in expected_pairs:
        matches = [
            rule for rule in rules if {rule.shadow_theme_a, rule.shadow_theme_b} == set(pair)
        ]
        assert len(matches) == 1, (
            f"expected exactly one shadow-interaction rule for theme pair "
            f"{tuple(pair)!r}, found {len(matches)}"
        )


def test_missing_manifest_raises_load_error(tmp_path: Path) -> None:
    (tmp_path / "relationship-frames").mkdir()
    with pytest.raises(RelationshipKnowledgeLoadError):
        load_relationship_frames_manifest(tmp_path)


def test_malformed_frame_raises_load_error(tmp_path: Path) -> None:
    frames_dir = tmp_path / "relationship-frames"
    frames_dir.mkdir()
    (frames_dir / "partner.yaml").write_text("relationship_type: PARTNER\n", encoding="utf-8")
    with pytest.raises(RelationshipKnowledgeLoadError):
        load_relationship_frame(tmp_path, "PARTNER")


def test_frame_type_mismatch_raises_load_error(tmp_path: Path) -> None:
    frames_dir = tmp_path / "relationship-frames"
    frames_dir.mkdir()
    (frames_dir / "family.yaml").write_text(
        "relationship_type: PARTNER\ndimensions: {}\n", encoding="utf-8"
    )
    with pytest.raises(RelationshipKnowledgeLoadError):
        load_relationship_frame(tmp_path, "FAMILY")
