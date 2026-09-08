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

import re

from pydantic import BaseModel, ConfigDict

from numra_interpretation.knowledge_loader import KnowledgeBase
from numra_interpretation.llm.types import ContextBlock, StructuredGenerationRequest
from numra_interpretation.llm.types import LLMProvider as LLMProviderProtocol
from numra_interpretation.llm.validator import (
    build_metric_display_value_index,
    build_special_claim_index,
)
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
    "numerology value. Do not calculate or derive an alternative value. All "
    "numerological claims must be grounded in the provided profile facts. Reference "
    "every numeric fact using the metric-placeholder syntax you were given, naming a "
    "known metric id for a single scalar fact or a known special id for a non-scalar "
    "fact such as hidden passion or karmic lessons, always prefixed with which person "
    "the fact belongs to (a for Person A, b for Person B), rather than typing digits "
    "yourself. Never type a numerology value as a literal digit. Do not state or "
    "imply a compatibility score, match percentage, or numeric rating of the "
    "relationship. Never use psychiatric, clinical, or personality-disorder language, "
    "and never frame an attachment style as a diagnosis — only as a descriptive, "
    "non-diagnostic reflection. Write 2-4 sentences of German prose for the 'text' "
    "field only."
)

_SHADOW_SYSTEM_INSTRUCTIONS = (
    "You are rendering one component of a symbolic, non-diagnostic shadow-dynamics "
    "reflection between two people, grounded entirely in the deterministic shadow "
    "theme(s) and interaction pattern you were given — you never choose or invent "
    "which shadow theme or interaction pattern applies, only explain the one given to "
    "you in natural German prose. All numerological claims must be grounded in the "
    "provided profile facts. Reference every numeric fact using the metric-placeholder "
    "syntax you were given, naming a known metric id for a single scalar fact or a "
    "known special id for a non-scalar fact such as hidden passion or karmic lessons, "
    "always prefixed with which person the fact belongs to (a for Person A, b for "
    "Person B), rather than typing digits yourself. Never type a numerology value as "
    "a literal digit. Do not state or imply a compatibility score or match "
    "percentage. Never use psychiatric, clinical, or personality-disorder language, "
    "and never frame an attachment style as a diagnosis. Write 2-4 sentences for the "
    "'text' field only."
)

#: Matches the two-profile-namespaced placeholder syntax this package requires:
#: ``{{metric:a:ID}}`` / ``{{metric:b:ID}}`` / ``{{special:a:ID}}`` / ``{{special:b:ID}}``.
#: Deliberately its own pattern rather than reusing
#: `numra_interpretation.llm.validator`'s single-profile pattern, which has no
#: namespace for *which* profile (A or B) a placeholder's id belongs to.
_PLACEHOLDER_PATTERN = re.compile(
    r"\{\{\s*(metric|special)\s*:\s*([ab])\s*:\s*([a-zA-Z0-9_]+)\s*\}\}"
)


def _resolve_placeholders(
    text: str, *, profile_a: CanonicalProfile, profile_b: CanonicalProfile
) -> str:
    """Two-profile-aware sibling of `numra_interpretation.report.pipeline`'s
    `_resolve_placeholders`: replaces every ``{{metric:a:ID}}``/``{{metric:b:ID}}``/
    ``{{special:a:ID}}``/``{{special:b:ID}}`` placeholder with the referenced profile's
    own canonical value — never with anything the LLM said. An unknown id (or an id
    that does not exist for the referenced profile) is a hard failure
    (`InvalidAnalysisSection`), retried once by the caller. A no-op when the text
    carries no placeholder syntax at all (e.g. `MockLLMProvider`'s output)."""
    indices: dict[tuple[str, str], dict[str, str]] = {
        ("metric", "a"): build_metric_display_value_index(profile_a),
        ("metric", "b"): build_metric_display_value_index(profile_b),
        ("special", "a"): build_special_claim_index(profile_a),
        ("special", "b"): build_special_claim_index(profile_b),
    }

    def _replace(match: re.Match[str]) -> str:
        namespace, profile_letter, identifier = match.group(1), match.group(2), match.group(3)
        source = indices[(namespace, profile_letter)]
        if identifier not in source:
            raise InvalidAnalysisSection(
                f"Unknown {namespace} id referenced by placeholder for profile "
                f"{profile_letter}: {identifier!r}"
            )
        return source[identifier]

    return _PLACEHOLDER_PATTERN.sub(_replace, text)


def _find_unauthorized_numeric_literals(
    text: str, *, profile_a: CanonicalProfile, profile_b: CanonicalProfile
) -> tuple[str, ...]:
    """Two-profile-aware sibling of
    `numra_interpretation.llm.validator.find_unauthorized_numeric_literals`: strips
    this package's own ``{{metric:a/b:ID}}``/``{{special:a/b:ID}}`` placeholder syntax
    first, then flags any remaining bare 2+-digit run that coincides with a canonical
    value from *either* profile — evidence the model typed a numerology fact (about
    Person A or Person B) as a literal digit instead of citing it via a placeholder."""
    stripped = _PLACEHOLDER_PATTERN.sub(" ", text)

    forbidden: set[str] = set()
    all_values = list(build_metric_display_value_index(profile_a).values())
    all_values += list(build_special_claim_index(profile_a).values())
    all_values += list(build_metric_display_value_index(profile_b).values())
    all_values += list(build_special_claim_index(profile_b).values())
    for value in all_values:
        for digits in re.findall(r"\d+", value):
            if len(digits) >= 2:
                forbidden.add(digits)

    found: list[str] = []
    seen: set[str] = set()
    for match in re.finditer(r"(?<!\d)\d{2,}(?!\d)", stripped):
        token = match.group(0)
        if token in forbidden and token not in seen:
            seen.add(token)
            found.append(token)
    return tuple(found)


def _validate_and_resolve_text(
    text: str,
    *,
    profile_a: CanonicalProfile,
    profile_b: CanonicalProfile,
    is_mock_provider: bool,
) -> str:
    """The grounding gate every rendered `ThemeStatement.text` must pass before it is
    accepted: first the unauthorized-literal check on the still-placeholder-bearing
    raw text (skipped for `MockLLMProvider`, exactly like
    `numra_interpretation.report.pipeline._generate_section` — its deterministic
    filler echoes raw grounding facts by design, which is not "the model inventing a
    claim"), then placeholder resolution against the real profile data. Raises
    `InvalidAnalysisSection` on either an unauthorized literal or an unknown
    placeholder id — the caller's existing one-repair-attempt pattern catches it."""
    if not is_mock_provider:
        unauthorized = _find_unauthorized_numeric_literals(
            text, profile_a=profile_a, profile_b=profile_b
        )
        if unauthorized:
            raise InvalidAnalysisSection(
                f"UnauthorizedNumericLiteral: text contains bare digit(s) {unauthorized!r} "
                "not referenced via a metric/special placeholder"
            )
    return _resolve_placeholders(text, profile_a=profile_a, profile_b=profile_b)


def _valid_placeholder_ids_block(
    valid_metric_ids: tuple[str, ...], valid_special_ids: tuple[str, ...]
) -> ContextBlock:
    """The ground-truth id listing a model actually needs to comply with the
    placeholder-only instruction above — same rationale as
    `numra_interpretation.report.pipeline._generate_section`'s
    ``valid_placeholder_ids`` block: naming which ids are known guarantees every id the
    model is told exists actually resolves. Ids here already carry their profile
    prefix (``a:``/``b:``, see `context.py`), so the model can tell which person's fact
    a given id belongs to."""
    return ContextBlock(
        role="instruction_supplement",
        label="valid_placeholder_ids",
        content=(
            "The only valid ids in the metric placeholder namespace are: "
            f"{', '.join(valid_metric_ids)}. "
            "The only valid ids in the special placeholder namespace are: "
            f"{', '.join(valid_special_ids)}. "
            "Each id already carries which person it describes as an 'a:' or 'b:' "
            "prefix. Never invent an id outside these two lists, even if it seems "
            "descriptive."
        ),
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
    profile_a: CanonicalProfile,
    profile_b: CanonicalProfile,
    llm: LLMProviderProtocol,
    attempt: int,
    is_mock_provider: bool,
) -> ThemeStatement:
    blocks = (
        context.profile_a_blocks
        + context.profile_b_blocks
        + context.dimension_blocks[dimension_id]
        + (_valid_placeholder_ids_block(context.valid_metric_ids, context.valid_special_ids),)
    )
    raw_text = await _render(
        llm=llm,
        system_instructions=_RELATIONSHIP_SYSTEM_INSTRUCTIONS,
        context_blocks=blocks,
        metadata={"dimension_id": dimension_id, "attempt": str(attempt)},
    )
    text = _validate_and_resolve_text(
        raw_text, profile_a=profile_a, profile_b=profile_b, is_mock_provider=is_mock_provider
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

    health = await llm.health()
    is_mock_provider = health.provider == "mock"

    dimensions: list[DimensionThemes] = []
    for dimension_id in frame_knowledge.dimensions:
        try:
            statement = await _generate_dimension_statement(
                context=context,
                dimension_id=dimension_id,
                profile_a=profile_a,
                profile_b=profile_b,
                llm=llm,
                attempt=1,
                is_mock_provider=is_mock_provider,
            )
        except InvalidAnalysisSection as exc:
            try:
                statement = await _generate_dimension_statement(
                    context=context,
                    dimension_id=dimension_id,
                    profile_a=profile_a,
                    profile_b=profile_b,
                    llm=llm,
                    attempt=2,
                    is_mock_provider=is_mock_provider,
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
    profile_a: CanonicalProfile,
    profile_b: CanonicalProfile,
    llm: LLMProviderProtocol,
    attempt: int,
    is_mock_provider: bool,
) -> ThemeStatement:
    blocks = profile_blocks + (
        ContextBlock(role="knowledge", label=label, content=base_content),
        _valid_placeholder_ids_block(
            shadow_context.valid_metric_ids, shadow_context.valid_special_ids
        ),
    )
    raw_text = await _render(
        llm=llm,
        system_instructions=_SHADOW_SYSTEM_INSTRUCTIONS,
        context_blocks=blocks,
        metadata={"component": label, "attempt": str(attempt)},
    )
    text = _validate_and_resolve_text(
        raw_text, profile_a=profile_a, profile_b=profile_b, is_mock_provider=is_mock_provider
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
    profile_a: CanonicalProfile,
    profile_b: CanonicalProfile,
    llm: LLMProviderProtocol,
    is_mock_provider: bool,
) -> ThemeStatement:
    try:
        return await _generate_shadow_statement(
            shadow_context=shadow_context,
            label=label,
            base_content=base_content,
            profile_blocks=profile_blocks,
            knowledge_ref=knowledge_ref,
            canonical_refs=canonical_refs,
            profile_a=profile_a,
            profile_b=profile_b,
            llm=llm,
            attempt=1,
            is_mock_provider=is_mock_provider,
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
                profile_a=profile_a,
                profile_b=profile_b,
                llm=llm,
                attempt=2,
                is_mock_provider=is_mock_provider,
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

    health = await llm.health()
    is_mock_provider = health.provider == "mock"

    user_a_statement = await _generate_shadow_statement_with_repair(
        shadow_context=shadow_context,
        label="user_a_shadow_theme",
        base_content=(f"Primäres Schattenthema von Person A: {shadow_context.shadow_theme_a}."),
        profile_blocks=shadow_context.profile_a_blocks,
        knowledge_ref=f"numbers#{shadow_context.shadow_theme_a}",
        canonical_refs=("metric:a:life_path",),
        profile_a=profile_a,
        profile_b=profile_b,
        llm=llm,
        is_mock_provider=is_mock_provider,
    )
    user_b_statement = await _generate_shadow_statement_with_repair(
        shadow_context=shadow_context,
        label="user_b_shadow_theme",
        base_content=(f"Primäres Schattenthema von Person B: {shadow_context.shadow_theme_b}."),
        profile_blocks=shadow_context.profile_b_blocks,
        knowledge_ref=f"numbers#{shadow_context.shadow_theme_b}",
        canonical_refs=("metric:b:life_path",),
        profile_a=profile_a,
        profile_b=profile_b,
        llm=llm,
        is_mock_provider=is_mock_provider,
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
        profile_a=profile_a,
        profile_b=profile_b,
        llm=llm,
        is_mock_provider=is_mock_provider,
    )
    escalation_statement = await _generate_shadow_statement_with_repair(
        shadow_context=shadow_context,
        label="escalation_loop",
        base_content=rule.escalation_loop_template,
        profile_blocks=shadow_context.profile_a_blocks + shadow_context.profile_b_blocks,
        knowledge_ref=knowledge_ref,
        canonical_refs=("metric:a:life_path", "metric:b:life_path"),
        profile_a=profile_a,
        profile_b=profile_b,
        llm=llm,
        is_mock_provider=is_mock_provider,
    )
    deescalation_statement = await _generate_shadow_statement_with_repair(
        shadow_context=shadow_context,
        label="deescalation_opportunity",
        base_content=rule.deescalation_template,
        profile_blocks=shadow_context.profile_a_blocks + shadow_context.profile_b_blocks,
        knowledge_ref=knowledge_ref,
        canonical_refs=("metric:a:life_path", "metric:b:life_path"),
        profile_a=profile_a,
        profile_b=profile_b,
        llm=llm,
        is_mock_provider=is_mock_provider,
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
