"""Loads and validates `knowledge/relationship-frames/**` and
`knowledge/shadow-interaction/**` into typed pydantic models — analogous to
`numra_interpretation.knowledge_loader`.

Core difference from the base package's `KnowledgeBase.number()`/`.metric()`: an
unknown relationship type is an *expected* case (e.g. `WORK` has no frame yet), so
`load_relationship_frame` returns ``None`` instead of raising — the service layer
turns that into a 409 `KnowledgeFrameNotAvailable`, not a 500.

Takes an explicit `knowledge_root: Path` for the same reason as the base package: this
must work whether invoked from the repo root, from inside this package, or bundled
into a deployed artifact with its own layout.
"""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]  # PyYAML ships no py.typed/stub in this repo's dependency set
from pydantic import ValidationError

from numra_relationship_interpretation.errors import RelationshipKnowledgeLoadError
from numra_relationship_interpretation.knowledge_models import (
    RelationshipFrameKnowledge,
    RelationshipKnowledgeManifest,
    ShadowInteractionManifest,
    ShadowInteractionRule,
)

__all__ = [
    "load_relationship_frame",
    "load_relationship_frames_manifest",
    "load_shadow_interaction_manifest",
    "load_shadow_interaction_rules",
]


def _load_yaml_file(path: Path) -> dict[str, object]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise RelationshipKnowledgeLoadError(
            f"Could not read knowledge file {path}: {exc}"
        ) from exc

    try:
        loaded = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise RelationshipKnowledgeLoadError(
            f"Invalid YAML in knowledge file {path}: {exc}"
        ) from exc

    if not isinstance(loaded, dict):
        raise RelationshipKnowledgeLoadError(
            f"Knowledge file {path} must contain a YAML mapping at the top level, "
            f"got {type(loaded).__name__}"
        )
    return loaded


def load_relationship_frames_manifest(knowledge_root: Path) -> RelationshipKnowledgeManifest:
    path = knowledge_root / "relationship-frames" / "manifest.yaml"
    data = _load_yaml_file(path)
    try:
        return RelationshipKnowledgeManifest.model_validate(data)
    except ValidationError as exc:
        raise RelationshipKnowledgeLoadError(f"Invalid manifest at {path}: {exc}") from exc


def load_relationship_frame(
    knowledge_root: Path, relationship_type: str
) -> RelationshipFrameKnowledge | None:
    """Look up the relationship frame for ``relationship_type`` (e.g. ``"PARTNER"``).

    Returns ``None`` — never raises — when no frame file exists for this type (e.g.
    `WORK`, `FAMILY` in this PR): a missing frame is an expected, non-exceptional
    case the service layer maps to a 409 `KnowledgeFrameNotAvailable`, in contrast to
    `numra_interpretation.knowledge_loader.KnowledgeBase.number()`'s hard-failure
    `KeyError` for a number that must always exist."""
    directory = knowledge_root / "relationship-frames"
    filename = relationship_type.lower() + ".yaml"
    path = directory / filename
    if not path.is_file():
        return None
    data = _load_yaml_file(path)
    try:
        frame = RelationshipFrameKnowledge.model_validate(data)
    except ValidationError as exc:
        raise RelationshipKnowledgeLoadError(
            f"Invalid relationship frame at {path}: {exc}"
        ) from exc
    if frame.relationship_type != relationship_type:
        raise RelationshipKnowledgeLoadError(
            f"Relationship frame at {path} declares relationship_type="
            f"{frame.relationship_type!r}, expected {relationship_type!r}"
        )
    return frame


def load_shadow_interaction_manifest(knowledge_root: Path) -> ShadowInteractionManifest:
    path = knowledge_root / "shadow-interaction" / "manifest.yaml"
    data = _load_yaml_file(path)
    try:
        return ShadowInteractionManifest.model_validate(data)
    except ValidationError as exc:
        raise RelationshipKnowledgeLoadError(f"Invalid manifest at {path}: {exc}") from exc


def load_shadow_interaction_rules(knowledge_root: Path) -> tuple[ShadowInteractionRule, ...]:
    """Load the deterministic `(shadow_theme_a, shadow_theme_b) -> template ids` lookup
    table from `knowledge/shadow-interaction/rules.yaml`. Raises
    `RelationshipKnowledgeLoadError` on malformed content — this table is required
    (shadow dynamics generation cannot fall back to "no rules")."""
    path = knowledge_root / "shadow-interaction" / "rules.yaml"
    data = _load_yaml_file(path)
    raw_rules = data.get("rules")
    if not isinstance(raw_rules, list):
        raise RelationshipKnowledgeLoadError(
            f"Shadow interaction rules file {path} must contain a top-level 'rules' list"
        )
    rules: list[ShadowInteractionRule] = []
    for entry in raw_rules:
        try:
            rules.append(ShadowInteractionRule.model_validate(entry))
        except ValidationError as exc:
            raise RelationshipKnowledgeLoadError(
                f"Invalid shadow interaction rule in {path}: {exc}"
            ) from exc
    return tuple(rules)
