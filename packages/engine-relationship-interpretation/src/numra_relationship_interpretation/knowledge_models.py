"""Typed pydantic models for validated `knowledge/relationship-frames/**` and
`knowledge/shadow-interaction/**` content — analogous to
`numra_interpretation.knowledge_models`. No calculation logic here, only shape
validation; a malformed file fails loudly via pydantic's own `ValidationError`,
wrapped by `knowledge_loader.py` into `RelationshipKnowledgeLoadError`.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RelationshipKnowledgeManifest(BaseModel):
    """`knowledge/relationship-frames/manifest.yaml`."""

    model_config = ConfigDict(frozen=True)

    knowledge_system: str
    version: str
    language: str


class DimensionKnowledge(BaseModel):
    """One dimension entry inside a relationship frame (e.g. `communication`).
    `number_modifiers` maps a Life Path display value ("1".."9", "11", "22", "33") to
    a short tone hint — deliberately short (not a full essay) since it only nudges
    the LLM's framing, the substantive grounding is `semantic_context_de`."""

    model_config = ConfigDict(frozen=True)

    semantic_context_de: str
    number_modifiers: dict[str, str]


class RelationshipFrameKnowledge(BaseModel):
    """A single file under `knowledge/relationship-frames/*.yaml` (e.g. `partner.yaml`).
    ``relationship_type`` must match one of `numra_api.models.enums.RelationshipType`'s
    values, but this package never imports the API's enum (MINIMAL TOUCH /
    dependency direction) — that cross-check is the API service layer's job."""

    model_config = ConfigDict(frozen=True)

    relationship_type: str
    dimensions: dict[str, DimensionKnowledge]


class ShadowInteractionManifest(BaseModel):
    """`knowledge/shadow-interaction/manifest.yaml`."""

    model_config = ConfigDict(frozen=True)

    knowledge_system: str
    version: str
    language: str


class ShadowInteractionRule(BaseModel):
    """One deterministic lookup row in `knowledge/shadow-interaction/rules.yaml`:
    given two shadow themes (one per profile, drawn from
    `numra_interpretation.knowledge_loader.KnowledgeBase.number(...).shadows`), names
    the template ids/text the pipeline renders — never computed or invented by the
    LLM itself, only rendered by it (specs/v2/shadow-dynamics-spec.md "Principle")."""

    model_config = ConfigDict(frozen=True)

    shadow_theme_a: str
    shadow_theme_b: str
    interaction_pattern_template_id: str
    escalation_loop_template: str
    deescalation_template: str
