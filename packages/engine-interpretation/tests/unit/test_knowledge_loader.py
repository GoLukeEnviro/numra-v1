from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from numra_interpretation.errors import KnowledgeLoadError
from numra_interpretation.knowledge_loader import KnowledgeLoader, load_knowledge_base
from numra_interpretation.knowledge_models import (
    AuthoringProvenance,
    KarmicDebtKnowledge,
    NumberKnowledge,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[4]
KNOWLEDGE_ROOT = REPO_ROOT / "knowledge"


def test_knowledge_root_resolves_from_repo_root() -> None:
    """The loader must not assume a fixed cwd — it takes an explicit path."""
    assert KNOWLEDGE_ROOT.is_dir(), f"expected {KNOWLEDGE_ROOT} to exist"
    kb = load_knowledge_base(KNOWLEDGE_ROOT)
    assert kb.manifest.knowledge_system == "numra"
    assert kb.manifest.version == "1.2.0"
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


# --- Wave 3 Schritt 1: optional long-form/governance fields -----------------------
#
# These fields are additive and absent-safe: existing knowledge/*.yaml content (no
# such keys at all) must keep loading unchanged, and a file that *does* carry them
# must validate and round-trip correctly. No real knowledge/ YAML is touched here —
# that migration is Wave 3 Schritt 2+.


def test_all_numbers_and_karmic_debts_carry_wave3_long_form_content() -> None:
    """Wave 3 Schritt 3: after the Schritt 2 pilot (master-numbers/22.yaml), all
    remaining numbers 1-9, the other two master numbers (11, 33), and all four karmic
    debts (13/4, 14/5, 16/7, 19/1) are migrated from numerology-analyst-agent's
    de-v3.json — every one of them must now carry real long-form content, not just
    pass schema validation with absent defaults."""
    kb = load_knowledge_base(KNOWLEDGE_ROOT)

    for value in list(range(1, 10)) + [11, 22, 33]:
        knowledge = kb.number(value)
        assert knowledge.constructive_expression, f"number {value} missing constructive_expression"
        assert knowledge.shadow_expression, f"number {value} missing shadow_expression"
        assert knowledge.development_theme, f"number {value} missing development_theme"
        assert len(knowledge.practical_suggestions) >= 1
        assert len(knowledge.counter_hypotheses) >= 1
        assert len(knowledge.reflection_prompts) >= 1
        assert knowledge.claim_class == "traditional_claim"
        assert "numra-tradition-v1" in knowledge.source_refs
        assert knowledge.authoring_provenance is not None
        assert knowledge.authoring_provenance.review_status == "draft"
        assert knowledge.stable_id is not None
        assert knowledge.classification in ("single", "master")
        assert len(knowledge.result_contexts) > 0
        # Greenfield fields (no source in the predecessor repo) are untouched by this
        # migration — still only the original short lists, per Wave 3 Schritt 3/4/5.
        assert len(knowledge.relationships) > 0
        assert len(knowledge.work_and_creation) > 0

    for value in (11, 33):
        assert kb.number(value).uncertainty == (
            "Meisterzahlen sind ein traditionelles Konzept ohne empirische Validierung."
        )

    for compound, (raw, reduced) in {
        "13/4": (13, 4),
        "14/5": (14, 5),
        "16/7": (16, 7),
        "19/1": (19, 1),
    }.items():
        debt = kb.karmic_debt(compound)
        assert debt is not None
        assert debt.raw_value == raw
        assert debt.reduced_value == reduced
        assert debt.constructive_expression, f"{compound} missing constructive_expression"
        assert debt.development_theme, f"{compound} missing development_theme"
        assert debt.claim_class == "traditional_claim"
        assert debt.uncertainty == (
            "Karmische Schuld ist ein traditionelles Konzept ohne empirische Validierung."
        )
        assert debt.authoring_provenance is not None

    assert kb.manifest.version == "1.2.0"
    assert kb.manifest.scientific_position is not None
    assert "nicht validiert" in kb.manifest.scientific_position


def test_master_22_pilot_content_unchanged_by_schritt3() -> None:
    """Regression guard for the Wave 3 Schritt 2 pilot card specifically — Schritt 3
    must not have (re)touched it."""
    kb = load_knowledge_base(KNOWLEDGE_ROOT)
    knowledge = kb.number(22)
    assert knowledge.stable_id == "de.pythagorean.v3.master.22"
    assert knowledge.development_theme == "Vision in Struktur überführen"


def test_number_knowledge_accepts_populated_long_form_fields(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    (root / "numbers").mkdir(parents=True)
    (root / "master-numbers").mkdir()
    (root / "karmic-debts").mkdir()
    (root / "metrics").mkdir()
    (root / "manifest.yaml").write_text(
        "knowledge_system: numra\n"
        "version: 1.1.0\n"
        "language: de\n"
        "scientific_position: >-\n"
        "  Numerologie ist empirisch nicht validiert.\n",
        encoding="utf-8",
    )
    payload = {
        "value": 2,
        "root": 2,
        "is_master": False,
        "core_themes": ["Kooperation"],
        "strengths": ["Sensibilitaet"],
        "shadows": ["Abhaengigkeit"],
        "relationships": ["Verbindung"],
        "work_and_creation": ["Teamarbeit"],
        "development": ["Diplomatie"],
        "cautions": ["Unentschlossenheit"],
        "stable_id": "de.pythagorean.v3.single.2",
        "classification": "single",
        "result_contexts": ["life_path_primary", "expression"],
        "constructive_expression": "Die Symbolik kann zu feinfuehliger Wahrnehmung einladen.",
        "shadow_expression": "Ueberbetonte Harmonie kann zu Selbstzuruecknahme fuehren.",
        "development_theme": "Kooperation und Abgrenzung",
        "practical_suggestions": ["Achte auf eigene Beduerfnisse."],
        "counter_hypotheses": ["Kooperationsbereitschaft kann anders erklaerbar sein."],
        "reflection_prompts": ["Wo erlebst du ausgewogenes Geben und Nehmen?"],
        "claim_class": "traditional_claim",
        "source_refs": ["numra-method-v2", "numra-tradition-v1"],
        "uncertainty": None,
        "authoring_provenance": {
            "authored_at": "2026-08-05",
            "author": "Numra Knowledge Team",
            "review_status": "draft",
        },
    }
    (root / "numbers" / "2.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")

    kb = KnowledgeLoader(root).load()
    knowledge = kb.number(2)

    assert isinstance(knowledge, NumberKnowledge)
    assert knowledge.stable_id == "de.pythagorean.v3.single.2"
    assert knowledge.result_contexts == ("life_path_primary", "expression")
    assert knowledge.constructive_expression == (
        "Die Symbolik kann zu feinfuehliger Wahrnehmung einladen."
    )
    assert knowledge.practical_suggestions == ("Achte auf eigene Beduerfnisse.",)
    assert knowledge.claim_class == "traditional_claim"
    assert isinstance(knowledge.authoring_provenance, AuthoringProvenance)
    assert knowledge.authoring_provenance.review_status == "draft"
    assert kb.manifest.scientific_position is not None
    assert "nicht validiert" in kb.manifest.scientific_position


def test_karmic_debt_knowledge_accepts_raw_and_reduced_value(tmp_path: Path) -> None:
    root = tmp_path / "knowledge"
    (root / "numbers").mkdir(parents=True)
    (root / "master-numbers").mkdir()
    (root / "karmic-debts").mkdir()
    (root / "metrics").mkdir()
    (root / "manifest.yaml").write_text(
        "knowledge_system: numra\nversion: 1.1.0\nlanguage: de\n", encoding="utf-8"
    )
    payload = {
        "compound": "13/4",
        "themes": ["Disziplin"],
        "raw_value": 13,
        "reduced_value": 4,
        "development_theme": "Disziplin als Weg zur Transformation",
    }
    (root / "karmic-debts" / "13-4.yaml").write_text(yaml.safe_dump(payload), encoding="utf-8")

    kb = KnowledgeLoader(root).load()
    debt = kb.karmic_debt("13/4")

    assert debt is not None
    assert isinstance(debt, KarmicDebtKnowledge)
    assert debt.raw_value == 13
    assert debt.reduced_value == 4
    assert debt.development_theme == "Disziplin als Weg zur Transformation"
