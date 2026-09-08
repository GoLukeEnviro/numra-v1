from __future__ import annotations

from pathlib import Path

import pytest

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


def test_load_unknown_relationship_type_returns_none() -> None:
    """WORK/FAMILY/etc. have no frame file in this PR -- expected, not an error."""
    assert load_relationship_frame(KNOWLEDGE_ROOT, "WORK") is None
    assert load_relationship_frame(KNOWLEDGE_ROOT, "OTHER") is None


def test_load_shadow_interaction_manifest() -> None:
    manifest = load_shadow_interaction_manifest(KNOWLEDGE_ROOT)
    assert manifest.knowledge_system == "numra-shadow-interaction"


def test_load_shadow_interaction_rules_covers_all_life_path_pairs() -> None:
    rules = load_shadow_interaction_rules(KNOWLEDGE_ROOT)
    # 9 choose 2 + 9 diagonal (same-theme) cases = 45.
    assert len(rules) == 45
    pairs = {frozenset((rule.shadow_theme_a, rule.shadow_theme_b)) for rule in rules}
    assert len(pairs) == 45
    for rule in rules:
        assert rule.interaction_pattern_template_id
        assert rule.escalation_loop_template.strip()
        assert rule.deescalation_template.strip()


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
