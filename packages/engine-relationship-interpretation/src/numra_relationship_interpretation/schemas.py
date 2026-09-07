"""Typed pydantic result shapes for relationship/shadow-dynamics analysis.

Mirrors `numra_interpretation.report.schemas`' shape philosophy: frozen models, no
compatibility score anywhere (specs/v2/relationship-type-spec.md "No compatibility
percentage"), and mandatory provenance on every free-text claim
(specs/v2/shadow-dynamics-spec.md).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

__all__ = [
    "DimensionThemes",
    "RelationshipAnalysisResult",
    "ShadowDynamicsResult",
    "ThemeStatement",
]


class ThemeStatement(BaseModel):
    """One provenance-carrying free-text statement. Every statement must be traceable
    back to canon values, curated knowledge, or (later) consented workspace evidence
    — `canonical_refs`/`knowledge_refs` never both empty (enforced by `linter.py`),
    `workspace_evidence_refs` always present, empty tuple if unused (never omitted,
    per specs/v2/shadow-dynamics-spec.md)."""

    model_config = ConfigDict(frozen=True)

    text: str
    canonical_refs: tuple[str, ...] = ()
    knowledge_refs: tuple[str, ...] = ()
    workspace_evidence_refs: tuple[str, ...] = ()


class DimensionThemes(BaseModel):
    """One relationship-frame dimension's generated statements (e.g. `communication`,
    `closeness`) — see `knowledge/relationship-frames/*.yaml`."""

    model_config = ConfigDict(frozen=True)

    dimension_id: str
    statements: tuple[ThemeStatement, ...]


class RelationshipAnalysisResult(BaseModel):
    """Top-level result of `pipeline.generate_relationship_analysis`. `dimensions`
    covers every dimension declared by the relationship type's frame — never a
    compatibility score, never a numeric match percentage."""

    model_config = ConfigDict(frozen=True)

    relationship_type: str
    dimensions: tuple[DimensionThemes, ...]
    calculation_version: str
    knowledge_version: str
    prompt_version: str
    model_provider: str
    model_name: str


class ShadowDynamicsResult(BaseModel):
    """Top-level result of `pipeline.generate_shadow_dynamics`. Shape fixed by
    specs/v2/shadow-dynamics-spec.md's `ShadowDynamicsResult` section."""

    model_config = ConfigDict(frozen=True)

    user_a_shadow_themes: tuple[ThemeStatement, ...]
    user_b_shadow_themes: tuple[ThemeStatement, ...]
    interaction_pattern: ThemeStatement
    escalation_loop: ThemeStatement
    deescalation_opportunities: tuple[ThemeStatement, ...]
    #: Coarse, non-numeric-score severity label (e.g. "low"/"moderate"/"high") — never
    #: a compatibility percentage.
    pattern_intensity: str
    recommended_micro_tasks: tuple[str, ...]
    calculation_version: str
    knowledge_version: str
    prompt_version: str
    model_provider: str
    model_name: str
