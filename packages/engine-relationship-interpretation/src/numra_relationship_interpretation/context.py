"""Deterministic assembly of `StructuredRelationshipContext` / `StructuredShadowContext`
(specs/v2/shadow-dynamics-spec.md pipeline diagram) -- no LLM call happens here. This
module decides which knowledge entries and which canonical facts the LLM renderer is
handed; the LLM's job (`pipeline.py`) is limited to rendering that closed context in
natural language, never inventing which theme applies.
"""

from __future__ import annotations

from numra_interpretation.knowledge_loader import KnowledgeBase
from numra_interpretation.llm.types import ContextBlock
from numra_interpretation.llm.validator import (
    build_metric_display_value_index,
    build_special_claim_index,
)
from numra_numerology.models.profile import CanonicalProfile
from numra_relationship_interpretation.knowledge_models import (
    RelationshipFrameKnowledge,
    ShadowInteractionRule,
)

__all__ = [
    "StructuredRelationshipContext",
    "StructuredShadowContext",
    "assemble_relationship_context",
    "assemble_shadow_context",
    "primary_shadow_theme",
]


class StructuredRelationshipContext:
    """Closed context the LLM renderer sees for `generate_relationship_analysis`: one
    block set per profile (A/B) plus one context block per frame dimension. Never
    carries the raw `CanonicalProfile` objects themselves -- only the already-resolved
    `ContextBlock`s the provider protocol accepts (see `numra_interpretation.llm.types`
    module docstring, "prompt-injection containment principle")."""

    def __init__(
        self,
        *,
        relationship_type: str,
        profile_a_blocks: tuple[ContextBlock, ...],
        profile_b_blocks: tuple[ContextBlock, ...],
        dimension_blocks: dict[str, tuple[ContextBlock, ...]],
        valid_metric_ids: tuple[str, ...],
        valid_special_ids: tuple[str, ...],
    ) -> None:
        self.relationship_type = relationship_type
        self.profile_a_blocks = profile_a_blocks
        self.profile_b_blocks = profile_b_blocks
        self.dimension_blocks = dimension_blocks
        self.valid_metric_ids = valid_metric_ids
        self.valid_special_ids = valid_special_ids


class StructuredShadowContext:
    """Closed context the LLM renderer sees for `generate_shadow_dynamics`: each
    profile's primary shadow theme plus the deterministic interaction-rule lookup
    already resolved -- the LLM never chooses which rule applies, only renders it."""

    def __init__(
        self,
        *,
        profile_a_blocks: tuple[ContextBlock, ...],
        profile_b_blocks: tuple[ContextBlock, ...],
        shadow_theme_a: str,
        shadow_theme_b: str,
        rule: ShadowInteractionRule,
        valid_metric_ids: tuple[str, ...],
        valid_special_ids: tuple[str, ...],
    ) -> None:
        self.profile_a_blocks = profile_a_blocks
        self.profile_b_blocks = profile_b_blocks
        self.shadow_theme_a = shadow_theme_a
        self.shadow_theme_b = shadow_theme_b
        self.rule = rule
        self.valid_metric_ids = valid_metric_ids
        self.valid_special_ids = valid_special_ids


def _profile_metric_blocks(
    profile: CanonicalProfile, *, label_prefix: str
) -> tuple[ContextBlock, ...]:
    """One `profile_fact` block per known scalar metric (life_path, expression, ...),
    labeled with `label_prefix` (``"a"``/``"b"``) so the renderer can distinguish which
    profile a fact belongs to -- reuses the base package's own ground-truth index
    (`build_metric_display_value_index`) rather than re-deriving display values."""
    index = build_metric_display_value_index(profile)
    return tuple(
        ContextBlock(
            role="profile_fact",
            label=f"{label_prefix}:{metric_id}",
            content=f"{metric_id} = {value}",
        )
        for metric_id, value in sorted(index.items())
    )


def _life_path_value(profile: CanonicalProfile) -> int:
    """The Life Path number's canonical root/master value -- used as the lookup key
    into `KnowledgeBase.number(...)` for both frame `number_modifiers` and shadow
    theme selection. Uses the already-computed `CalculationMetric.value`, never
    re-derives from raw birth data (no calculation logic in this package)."""
    return int(profile.core_numbers.life_path.effective_value)


def primary_shadow_theme(profile: CanonicalProfile, knowledge: KnowledgeBase) -> str:
    """The deterministic primary shadow theme for a profile: the first entry of its
    Life Path number's ``shadows`` list (see `knowledge/numbers/*.yaml`). A
    deliberate simplification of the full shadows list down to one representative
    theme, documented in `knowledge/shadow-interaction/rules.yaml`'s header comment
    -- keeps the interaction-rule lookup table at 45 rows (9 choose 2 + diagonal)
    instead of combinatorially exploding across every shadows-list entry."""
    life_path = _life_path_value(profile)
    number_knowledge = knowledge.number(life_path)
    if not number_knowledge.shadows:
        raise ValueError(f"NUMRA knowledge for Life Path {life_path} has an empty shadows list")
    return number_knowledge.shadows[0]


def assemble_relationship_context(
    *,
    profile_a: CanonicalProfile,
    profile_b: CanonicalProfile,
    frame: RelationshipFrameKnowledge,
) -> StructuredRelationshipContext:
    """Deterministic assembly for `pipeline.generate_relationship_analysis`. Every
    dimension in `frame.dimensions` gets its own `ContextBlock` set: the dimension's
    `semantic_context_de` text plus each profile's Life-Path-specific
    `number_modifiers` hint, if one is declared for that Life Path value."""
    profile_a_blocks = _profile_metric_blocks(profile_a, label_prefix="a")
    profile_b_blocks = _profile_metric_blocks(profile_b, label_prefix="b")

    life_path_a = str(_life_path_value(profile_a))
    life_path_b = str(_life_path_value(profile_b))

    dimension_blocks: dict[str, tuple[ContextBlock, ...]] = {}
    for dimension_id, dimension in frame.dimensions.items():
        blocks = [
            ContextBlock(
                role="knowledge",
                label=f"{dimension_id}:semantic_context",
                content=dimension.semantic_context_de,
            )
        ]
        modifier_a = dimension.number_modifiers.get(life_path_a)
        if modifier_a:
            blocks.append(
                ContextBlock(
                    role="knowledge", label=f"{dimension_id}:a_number_modifier", content=modifier_a
                )
            )
        modifier_b = dimension.number_modifiers.get(life_path_b)
        if modifier_b:
            blocks.append(
                ContextBlock(
                    role="knowledge", label=f"{dimension_id}:b_number_modifier", content=modifier_b
                )
            )
        dimension_blocks[dimension_id] = tuple(blocks)

    valid_metric_ids = sorted(
        [f"a:{metric_id}" for metric_id in build_metric_display_value_index(profile_a)]
        + [f"b:{metric_id}" for metric_id in build_metric_display_value_index(profile_b)]
    )
    valid_special_ids = sorted(
        [f"a:{special_id}" for special_id in build_special_claim_index(profile_a)]
        + [f"b:{special_id}" for special_id in build_special_claim_index(profile_b)]
    )

    return StructuredRelationshipContext(
        relationship_type=frame.relationship_type,
        profile_a_blocks=profile_a_blocks,
        profile_b_blocks=profile_b_blocks,
        dimension_blocks=dimension_blocks,
        valid_metric_ids=tuple(valid_metric_ids),
        valid_special_ids=tuple(valid_special_ids),
    )


def assemble_shadow_context(
    *,
    profile_a: CanonicalProfile,
    profile_b: CanonicalProfile,
    knowledge: KnowledgeBase,
    shadow_rules: tuple[ShadowInteractionRule, ...],
) -> StructuredShadowContext:
    """Deterministic assembly for `pipeline.generate_shadow_dynamics`. Resolves each
    profile's `primary_shadow_theme`, then the single matching rule from
    `shadow_rules` (order-independent -- ``(a, b)`` and ``(b, a)`` both match the
    same stored row). Raises `ValueError` if no rule matches -- the rules table is
    required to be exhaustive over every Life-Path-pair combination (see
    `knowledge/shadow-interaction/rules.yaml`'s header comment), so a miss indicates
    a knowledge-content gap, not a normal runtime case to fall back from silently."""
    theme_a = primary_shadow_theme(profile_a, knowledge)
    theme_b = primary_shadow_theme(profile_b, knowledge)

    rule = next(
        (r for r in shadow_rules if {r.shadow_theme_a, r.shadow_theme_b} == {theme_a, theme_b}),
        None,
    )
    if rule is None:
        raise ValueError(
            f"No shadow interaction rule found for theme pair ({theme_a!r}, {theme_b!r})"
        )

    profile_a_blocks = _profile_metric_blocks(profile_a, label_prefix="a")
    profile_b_blocks = _profile_metric_blocks(profile_b, label_prefix="b")

    valid_metric_ids = sorted(
        [f"a:{metric_id}" for metric_id in build_metric_display_value_index(profile_a)]
        + [f"b:{metric_id}" for metric_id in build_metric_display_value_index(profile_b)]
    )
    valid_special_ids = sorted(
        [f"a:{special_id}" for special_id in build_special_claim_index(profile_a)]
        + [f"b:{special_id}" for special_id in build_special_claim_index(profile_b)]
    )

    return StructuredShadowContext(
        profile_a_blocks=profile_a_blocks,
        profile_b_blocks=profile_b_blocks,
        shadow_theme_a=theme_a,
        shadow_theme_b=theme_b,
        rule=rule,
        valid_metric_ids=tuple(valid_metric_ids),
        valid_special_ids=tuple(valid_special_ids),
    )
