from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from numra_interpretation.errors import KnowledgeLoadError
from numra_interpretation.knowledge_loader import KnowledgeLoader, load_knowledge_base

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[4]
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"


def test_knowledge_root_resolves_from_repo_root() -> None:
    """The loader must not assume a fixed cwd — it takes an explicit path."""
    assert KNOWLEDGE_ROOT.is_dir(), f"expected {KNOWLEDGE_ROOT} to exist"
    kb = load_knowledge_base(KNOWLEDGE_ROOT)
    assert kb.manifest.knowledge_system == "numra"
    assert kb.manifest.version == "1.1.0"
    assert kb.manifest.language == "de"


def test_all_numbers_1_to_9_load() -> None:
    kb = load_knowledge_base(KNOWLEDGE_ROOT)
    for value in range(1, 10):
        knowledge = kb.number(value)
        assert knowledge.value == value
        assert knowledge.is_master is False
        assert len(knowledge.core_themes) > 0
        assert len(knowledge.shadows) > 0
        assert len(knowledge.strengths) > 0
        assert len(knowledge.relationships) > 0
        assert len(knowledge.work_and_creation) > 0
        assert len(knowledge.development) > 0
        assert len(knowledge.cautions) > 0


def test_all_master_numbers_load() -> None:
    kb = load_knowledge_base(KNOWLEDGE_ROOT)
    for value in (11, 22, 33):
        knowledge = kb.number(value)
        assert knowledge.value == value
        assert knowledge.is_master is True
        assert knowledge.root in range(1, 10)


def test_unknown_number_raises_key_error() -> None:
    kb = load_knowledge_base(KNOWLEDGE_ROOT)
    with pytest.raises(KeyError):
        kb.number(44)


def test_karmic_debts_load_exactly_the_allowlisted_four() -> None:
    kb = load_knowledge_base(KNOWLEDGE_ROOT)
    for compound in ("13/4", "14/5", "16/7", "19/1"):
        debt = kb.karmic_debt(compound)
        assert debt is not None
        assert debt.compound == compound
        assert len(debt.themes) > 0


def test_karmic_debt_outside_allowlist_returns_none_not_error() -> None:
    kb = load_knowledge_base(KNOWLEDGE_ROOT)
    assert kb.karmic_debt("31/4") is None


ALL_METRIC_IDS = (
    "life_path",
    "birthday",
    "attitude",
    "expression",
    "soul_urge",
    "personality",
    "maturity",
    "balance",
    "hidden_passion",
    "karmic_lessons",
    "subconscious_self",
    "cornerstone",
    "capstone",
    "first_vowel",
    "intensity_table",
    "pinnacle",
    "challenge",
    "personal_year",
    "personal_month",
    "personal_day",
)


def test_all_expected_metrics_load() -> None:
    kb = load_knowledge_base(KNOWLEDGE_ROOT)
    for metric_id in ALL_METRIC_IDS:
        metric = kb.metric(metric_id)
        assert metric.metric_id == metric_id
        assert metric.display_name_de
        assert metric.semantic_context_de
    assert kb.known_metric_ids == frozenset(ALL_METRIC_IDS)


def test_soul_urge_and_life_path_semantic_context_differ() -> None:
    """Distinct metric semantics must not collapse to the same text even when the
    numbers coincide (this is about the metric's meaning, not the number's)."""
    kb = load_knowledge_base(KNOWLEDGE_ROOT)
    soul_urge = kb.metric("soul_urge")
    life_path = kb.metric("life_path")
    assert soul_urge.semantic_context_de != life_path.semantic_context_de
    assert soul_urge.display_name_de != life_path.display_name_de


def test_unknown_metric_raises_key_error() -> None:
    kb = load_knowledge_base(KNOWLEDGE_ROOT)
    with pytest.raises(KeyError):
        kb.metric("not_a_real_metric")


def test_missing_knowledge_root_raises_clear_error(tmp_path: Path) -> None:
    with pytest.raises(KnowledgeLoadError, match="does not exist"):
        load_knowledge_base(tmp_path / "does-not-exist")


def test_malformed_yaml_raises_clear_error(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    (root / "manifest.yaml").write_text(
        "knowledge_system: numra\nversion: 1.0.0\nlanguage: de\n", encoding="utf-8"
    )
    (root / "numbers").mkdir()
    (root / "master-numbers").mkdir()
    (root / "karmic-debts").mkdir()
    (root / "metrics").mkdir()
    (root / "numbers" / "1.yaml").write_text("not: [valid, - broken\n", encoding="utf-8")

    with pytest.raises(KnowledgeLoadError, match="Invalid YAML"):
        KnowledgeLoader(root).load()


def test_missing_required_field_raises_clear_error(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    root.mkdir()
    (root / "manifest.yaml").write_text(
        "knowledge_system: numra\nversion: 1.0.0\nlanguage: de\n", encoding="utf-8"
    )
    (root / "numbers").mkdir()
    (root / "master-numbers").mkdir()
    (root / "karmic-debts").mkdir()
    (root / "metrics").mkdir()
    # missing several required NumberKnowledge fields (shadows, relationships, ...)
    (root / "numbers" / "1.yaml").write_text(
        yaml.safe_dump({"value": 1, "root": 1, "is_master": False, "core_themes": ["x"]}),
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeLoadError, match="Invalid number knowledge"):
        KnowledgeLoader(root).load()


def test_duplicate_number_value_raises_clear_error(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    (root / "numbers").mkdir(parents=True)
    (root / "master-numbers").mkdir()
    (root / "karmic-debts").mkdir()
    (root / "metrics").mkdir()
    (root / "manifest.yaml").write_text(
        "knowledge_system: numra\nversion: 1.0.0\nlanguage: de\n", encoding="utf-8"
    )
    number_payload = {
        "value": 1,
        "root": 1,
        "is_master": False,
        "core_themes": ["a"],
        "strengths": ["a"],
        "shadows": ["a"],
        "relationships": ["a"],
        "work_and_creation": ["a"],
        "development": ["a"],
        "cautions": ["a"],
    }
    (root / "numbers" / "1.yaml").write_text(yaml.safe_dump(number_payload), encoding="utf-8")
    (root / "numbers" / "1-again.yaml").write_text(yaml.safe_dump(number_payload), encoding="utf-8")

    with pytest.raises(KnowledgeLoadError, match="Duplicate number knowledge"):
        KnowledgeLoader(root).load()


def test_non_mapping_yaml_top_level_raises_clear_error(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    (root / "numbers").mkdir(parents=True)
    (root / "master-numbers").mkdir()
    (root / "karmic-debts").mkdir()
    (root / "metrics").mkdir()
    (root / "manifest.yaml").write_text("- just\n- a\n- list\n", encoding="utf-8")

    with pytest.raises(KnowledgeLoadError, match="YAML mapping"):
        KnowledgeLoader(root).load()
