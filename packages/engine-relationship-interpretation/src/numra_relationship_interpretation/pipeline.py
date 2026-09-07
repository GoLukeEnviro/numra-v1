"""Prompt + parse + validate + one-repair-attempt pipeline for relationship analysis
and shadow dynamics — the exact pattern of
`numra_interpretation.report.pipeline.generate_report`'s
``except InvalidReportSection: # one repair attempt``, applied to
`InvalidAnalysisSection` here.

No calculation happens here. Every fact handed to the LLM comes from the already
deterministically assembled `StructuredRelationshipContext`/`StructuredShadowContext`
(`context.py`); the LLM's only job is rendering that closed context into natural
German prose (specs/v2/shadow-dynamics-spec.md "LLM Renderer" step) — it never
chooses which knowledge entry or which shadow-interaction rule applies.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from numra_interpretation.knowledge_loader import KnowledgeBase
from numra_interpretation.llm.types import ContextBlock, StructuredGenerationRequest
from numra_interpretation.llm.types import LLMProvider as LLMProviderProtocol
from numra_numerology.models.profile import CanonicalProfile
from numra_relationship_interpretation.context import (
    StructuredRelationshipContext,
    StructuredShadowContext,
    assemble_relationship_context,
    assemble_shadow_context,
)
from numra_relationship_interpretation.errors import AnalysisGenerationError, InvalidAnalysisSection
from numra_relationship_interpretation.knowledge_models import (
    RelationshipFrameKnowledge,
    ShadowInteractionRule,
)
from numra_relationship_interpretation.linter import (
    validate_no_compatibility_score,
    validate_no_forbidden_language,
    validate_provenance_coverage,
)
from numra_relationship_interpretation.schemas import (
    DimensionThemes,
    RelationshipAnalysisResult,
    ShadowDynamicsResult,
    ThemeStatement,
)

__all__ = ["generate_relationship_analysis", "generate_shadow_dynamics"]

#: Bumped whenever the prompt shape/instructions here change materially — snapshotted
#: onto every persisted analysis, same role as
#: `numra_api.services.report_service.PROMPT_VERSION`.
PROMPT_VERSION = "numra-relationship-v1"

_RELATIONSHIP_SYSTEM_INSTRUCTIONS = (
    "You are rendering a non-diagnostic, symbolic numerology relationship reflection "
    "for exactly one dimension, grounded entirely in the profile facts and knowledge "
    "context you were given. Do not invent a Life Path, Expression, or any other "
    "numerology value. Do not state or imply a compatibility score, match percentage, "
    "or numeric rating of the relationship. Never use psychiatric, clinical, or "
    "personality-disorder language, and never frame an attachment style as a "
    "diagnosis — only as a descriptive, non-diagnostic reflection. Write 2-4 sentences "
    "of German prose for the 'text' field only."
)

_SHADOW_SYSTEM_INSTRUCTIONS = (
    "You are rendering one component of a symbolic, non-diagnostic shadow-dynamics "
    "reflection between two people, grounded entirely in the deterministic shadow "
    "theme(s) and interaction pattern you were given — you never choose or invent "
    "which shadow theme or interaction pattern applies, only explain the one given to "
    "you in natural German prose. Do not state or imply a compatibility score or "
    "match percentage. Never use psychiatric, clinical, or personality-disorder "
    "language, and never frame an attachment style as a diagnosis. Write 2-4 sentences "
    "for the 'text' field only."
)


class _GeneratedText(BaseModel):
    """The minimal structured-generation target shared by every rendering call in this
    pipeline — a single ``text`` field, deliberately the exact convention
    `numra_interpretation.llm.mock_provider.MockLLMProvider.generate_structured`
    already knows how to fill, so tests exercise the same schema shape a real
    provider call would use."""

    model_config = ConfigDict(frozen=True)

    text: str


async def _render(
    *,
    llm: LLMProviderProtocol,
    system_instructions: str,
    context_blocks: tuple[ContextBlock, ...],
    metadata: dict[str, str],
) -> str:
    request = StructuredGenerationRequest(
        system_instructions=system_instructions,
        context_blocks=context_blocks,
        metadata=metadata,
        target_schema_name="GeneratedText",
    )
    result = await llm.generate_structured(request, _GeneratedText)
    assert isinstance(result, _GeneratedText)
    return result.text


async def _generate_dimension_statement(
    *,
    context: StructuredRelationshipContext,
    dimension_id: str,
    llm: LLMProviderProtocol,
    attempt: int,
) -> ThemeStatement:
    blocks = (
        context.profile_a_blocks + context.profile_b_blocks + context.dimension_blocks[dimension_id]
    )
    text = await _render(
        llm=llm,
        system_instructions=_RELATIONSHIP_SYSTEM_INSTRUCTIONS,
        context_blocks=blocks,
        metadata={"dimension_id": dimension_id, "attempt": str(attempt)},
    )

    # Provenance is attached deterministically by the pipeline, never trusted from the
    # LLM's own output — the pipeline itself already knows, from the (non-LLM)
    # `StructuredRelationshipContext` assembly, exactly which canonical facts and
    # which knowledge entry grounded this statement (specs/v2/shadow-dynamics-spec.md
    # "Principle": "The LLM never invents shadow themes... every theme statement must
    # carry provenance"). This also guarantees `validate_provenance_coverage` can
    # never fail for a reason outside the pipeline's own control.
    statement = ThemeStatement(
        text=text,
        canonical_refs=("metric:a:life_path", "metric:b:life_path"),
        knowledge_refs=(f"relationship-frames/{context.relationship_type}#{dimension_id}",),
    )
    validate_provenance_coverage((statement,))
    validate_no_forbidden_language(statement)
    validate_no_compatibility_score(statement)
    return statement


async def generate_relationship_analysis(
    *,
    profile_a: CanonicalProfile,
    profile_b: CanonicalProfile,
    relationship_type: str,
    frame_knowledge: RelationshipFrameKnowledge,
    llm: LLMProviderProtocol,
    knowledge_version: str,
) -> RelationshipAnalysisResult:
    """Run the relationship-analysis pipeline: deterministic context assembly ->
    one rendering call per frame dimension -> validate -> assemble. Raises
    `AnalysisGenerationError` if a dimension still fails validation after the one
    permitted repair attempt."""
    if frame_knowledge.relationship_type != relationship_type:
        raise ValueError(
            f"frame_knowledge.relationship_type={frame_knowledge.relationship_type!r} "
            f"does not match requested relationship_type={relationship_type!r}"
        )

    context = assemble_relationship_context(
        profile_a=profile_a, profile_b=profile_b, frame=frame_knowledge
    )

    dimensions: list[DimensionThemes] = []
    for dimension_id in frame_knowledge.dimensions:
        try:
            statement = await _generate_dimension_statement(
                context=context, dimension_id=dimension_id, llm=llm, attempt=1
            )
        except InvalidAnalysisSection as exc:
            try:
                statement = await _generate_dimension_statement(
                    context=context, dimension_id=dimension_id, llm=llm, attempt=2
                )
            except InvalidAnalysisSection as retry_exc:
                raise AnalysisGenerationError(
                    f"ANALYSIS_VALIDATION_FAILED: dimension {dimension_id!r} failed "
                    f"twice: first={exc}; retry={retry_exc}"
                ) from retry_exc
        dimensions.append(DimensionThemes(dimension_id=dimension_id, statements=(statement,)))

    health = await llm.health()
    return RelationshipAnalysisResult(
        relationship_type=relationship_type,
        dimensions=tuple(dimensions),
        calculation_version=profile_a.calculation_version,
        knowledge_version=knowledge_version,
        prompt_version=PROMPT_VERSION,
        model_provider=health.provider,
        model_name="mock-v1" if health.provider == "mock" else health.provider,
    )


async def _generate_shadow_statement(
    *,
    shadow_context: StructuredShadowContext,
    label: str,
    base_content: str,
    profile_blocks: tuple[ContextBlock, ...],
    knowledge_ref: str,
    canonical_refs: tuple[str, ...],
    llm: LLMProviderProtocol,
    attempt: int,
) -> ThemeStatement:
    blocks = profile_blocks + (ContextBlock(role="knowledge", label=label, content=base_content),)
    text = await _render(
        llm=llm,
        system_instructions=_SHADOW_SYSTEM_INSTRUCTIONS,
        context_blocks=blocks,
        metadata={"component": label, "attempt": str(attempt)},
    )
    statement = ThemeStatement(
        text=text, canonical_refs=canonical_refs, knowledge_refs=(knowledge_ref,)
    )
    validate_provenance_coverage((statement,))
    validate_no_forbidden_language(statement)
    validate_no_compatibility_score(statement)
    return statement


async def _generate_shadow_statement_with_repair(
    *,
    shadow_context: StructuredShadowContext,
    label: str,
    base_content: str,
    profile_blocks: tuple[ContextBlock, ...],
    knowledge_ref: str,
    canonical_refs: tuple[str, ...],
    llm: LLMProviderProtocol,
) -> ThemeStatement:
    try:
        return await _generate_shadow_statement(
            shadow_context=shadow_context,
            label=label,
            base_content=base_content,
            profile_blocks=profile_blocks,
            knowledge_ref=knowledge_ref,
            canonical_refs=canonical_refs,
            llm=llm,
            attempt=1,
        )
    except InvalidAnalysisSection as exc:
        try:
            return await _generate_shadow_statement(
                shadow_context=shadow_context,
                label=label,
                base_content=base_content,
                profile_blocks=profile_blocks,
                knowledge_ref=knowledge_ref,
                canonical_refs=canonical_refs,
                llm=llm,
                attempt=2,
            )
        except InvalidAnalysisSection as retry_exc:
            raise AnalysisGenerationError(
                f"ANALYSIS_VALIDATION_FAILED: component {label!r} failed twice: "
                f"first={exc}; retry={retry_exc}"
            ) from retry_exc


def _pattern_intensity(shadow_context: StructuredShadowContext) -> str:
    """Deterministic, non-numeric-score severity label — never a compatibility
    percentage (specs/v2/relationship-type-spec.md). Both profiles sharing the same
    primary shadow theme is read as a mutually-reinforcing (higher-intensity) pattern
    per `knowledge/shadow-interaction/rules.yaml`'s diagonal-case escalation text;
    every other pairing is read as moderate."""
    if shadow_context.shadow_theme_a == shadow_context.shadow_theme_b:
        return "high"
    return "moderate"


def _recommended_micro_tasks(shadow_context: StructuredShadowContext) -> tuple[str, ...]:
    """Deterministic (not LLM-generated) micro-task suggestions derived directly from
    the resolved rule's own template text — kept short and actionable, never invented
    per-call so the same theme pair always yields the same tasks."""
    theme_a, theme_b = shadow_context.shadow_theme_a, shadow_context.shadow_theme_b
    return (
        f"Die eigene Neigung zu {theme_a} bewusst benennen, bevor sie automatisch wird.",
        f"Die Neigung des Gegenübers zu {theme_b} als Muster erkennen, "
        "nicht als persönlichen Angriff.",
    )


async def generate_shadow_dynamics(
    *,
    profile_a: CanonicalProfile,
    profile_b: CanonicalProfile,
    relationship_type: str,
    knowledge: KnowledgeBase,
    shadow_rules: tuple[ShadowInteractionRule, ...],
    llm: LLMProviderProtocol,
    knowledge_version: str,
) -> ShadowDynamicsResult:
    """Run the shadow-dynamics pipeline (specs/v2/shadow-dynamics-spec.md pipeline
    diagram): deterministic context assembly -> per-component rendering -> validate
    -> assemble. Type-agnostic over `relationship_type` (kept only as result metadata)
    — the shadow-interaction rules table itself is not relationship-type-scoped."""
    shadow_context = assemble_shadow_context(
        profile_a=profile_a, profile_b=profile_b, knowledge=knowledge, shadow_rules=shadow_rules
    )
    rule = shadow_context.rule
    knowledge_ref = f"shadow-interaction/rules.yaml#{rule.interaction_pattern_template_id}"

    user_a_statement = await _generate_shadow_statement_with_repair(
        shadow_context=shadow_context,
        label="user_a_shadow_theme",
        base_content=(f"Primäres Schattenthema von Person A: {shadow_context.shadow_theme_a}."),
        profile_blocks=shadow_context.profile_a_blocks,
        knowledge_ref=f"numbers#{shadow_context.shadow_theme_a}",
        canonical_refs=("metric:a:life_path",),
        llm=llm,
    )
    user_b_statement = await _generate_shadow_statement_with_repair(
        shadow_context=shadow_context,
        label="user_b_shadow_theme",
        base_content=(f"Primäres Schattenthema von Person B: {shadow_context.shadow_theme_b}."),
        profile_blocks=shadow_context.profile_b_blocks,
        knowledge_ref=f"numbers#{shadow_context.shadow_theme_b}",
        canonical_refs=("metric:b:life_path",),
        llm=llm,
    )
    interaction_statement = await _generate_shadow_statement_with_repair(
        shadow_context=shadow_context,
        label="interaction_pattern",
        base_content=(
            f"Interaktionsmuster {rule.interaction_pattern_template_id}: "
            f"{shadow_context.shadow_theme_a} trifft auf {shadow_context.shadow_theme_b}."
        ),
        profile_blocks=shadow_context.profile_a_blocks + shadow_context.profile_b_blocks,
        knowledge_ref=knowledge_ref,
        canonical_refs=("metric:a:life_path", "metric:b:life_path"),
        llm=llm,
    )
    escalation_statement = await _generate_shadow_statement_with_repair(
        shadow_context=shadow_context,
        label="escalation_loop",
        base_content=rule.escalation_loop_template,
        profile_blocks=shadow_context.profile_a_blocks + shadow_context.profile_b_blocks,
        knowledge_ref=knowledge_ref,
        canonical_refs=("metric:a:life_path", "metric:b:life_path"),
        llm=llm,
    )
    deescalation_statement = await _generate_shadow_statement_with_repair(
        shadow_context=shadow_context,
        label="deescalation_opportunity",
        base_content=rule.deescalation_template,
        profile_blocks=shadow_context.profile_a_blocks + shadow_context.profile_b_blocks,
        knowledge_ref=knowledge_ref,
        canonical_refs=("metric:a:life_path", "metric:b:life_path"),
        llm=llm,
    )

    health = await llm.health()
    return ShadowDynamicsResult(
        user_a_shadow_themes=(user_a_statement,),
        user_b_shadow_themes=(user_b_statement,),
        interaction_pattern=interaction_statement,
        escalation_loop=escalation_statement,
        deescalation_opportunities=(deescalation_statement,),
        pattern_intensity=_pattern_intensity(shadow_context),
        recommended_micro_tasks=_recommended_micro_tasks(shadow_context),
        calculation_version=profile_a.calculation_version,
        knowledge_version=knowledge_version,
        prompt_version=PROMPT_VERSION,
        model_provider=health.provider,
        model_name="mock-v1" if health.provider == "mock" else health.provider,
    )
