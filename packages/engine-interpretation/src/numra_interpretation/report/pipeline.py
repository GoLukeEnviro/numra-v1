"""The AgentWrite pipeline (master prompt §103-§104): Canonical Profile + Knowledge +
Report Manifest -> per-section structured generation (with global context carried
forward) -> per-section validation -> assembly -> global lint -> `StructuredReport`.

No calculation happens here. Every numeric fact the pipeline hands to the LLM comes
from the already-computed `CanonicalProfile`; every numeric claim the LLM makes back is
checked against that same profile before being accepted.
"""

from __future__ import annotations

import re

from numra_interpretation.composer import CORE_METRIC_IDS, TIMING_METRIC_IDS, compose_section
from numra_interpretation.errors import InvalidReportSection
from numra_interpretation.knowledge_loader import KnowledgeBase
from numra_interpretation.llm.types import (
    ContextBlock,
    NumericClaim,
    StructuredGenerationRequest,
)
from numra_interpretation.llm.types import LLMProvider as LLMProviderProtocol
from numra_interpretation.llm.validator import (
    build_metric_display_value_index,
    build_special_claim_index,
    find_unauthorized_numeric_literals,
    validate_metric_ref_coverage,
    validate_numeric_claims,
)
from numra_interpretation.report.content_padding import deterministic_elaboration
from numra_interpretation.report.linter import lint_report
from numra_interpretation.report.manifest import ReportManifest, ReportSectionSpec
from numra_interpretation.report.schemas import (
    GeneratedSectionContent,
    ReportOutline,
    StructuredReport,
    StructuredReportSection,
)
from numra_numerology.models.metric import CalculationMetric
from numra_numerology.models.profile import CanonicalProfile

__all__ = ["ReportGenerationError", "generate_report"]

_SYSTEM_INSTRUCTIONS = (
    "Use only the canonical numerological values supplied by the engine. Do not "
    "calculate numerological values. Do not derive alternative values. Do not modify "
    "a metric. Do not replace a metric. Do not infer missing metrics. If a metric is "
    "unavailable, state that it is unavailable. All numerological claims must be "
    "grounded in the provided Canonical Profile and Knowledge documents. Reference "
    "every numeric fact using the metric-placeholder syntax you were given, naming a "
    "known metric id for a single scalar fact or a known special id for a non-scalar "
    "fact such as hidden passion or karmic lessons, rather than typing digits "
    "yourself. Never type a numerology value as a literal digit."
)

_OUTLINE_SYSTEM_INSTRUCTIONS = (
    "Plan a short focus statement for each report section listed below. Do not write "
    "the sections themselves and do not state any numerological value, literal or "
    "otherwise — this is a structural outline only, grounded purely in which themes "
    "each section should emphasize given the Canonical Profile facts provided."
)

#: Report types long enough to benefit from an upfront structural outline (master
#: prompt §102-ish "AgentWrite" planning step) before per-section generation begins.
#: QUICK reports are short enough that the manifest's own section list is already the
#: outline.
_OUTLINE_REPORT_TYPES = ("FULL", "ULTIMATE")


class ReportGenerationError(Exception):
    """Raised when the pipeline cannot produce a REPORT_STATUS=VALID report, even after
    the one permitted repair attempt (master prompt §100)."""


_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*(metric|special)\s*:\s*([a-zA-Z0-9_]+)\s*\}\}")


def _resolve_placeholders(text: str, profile: CanonicalProfile) -> str:
    """The renderer step from master prompt §99: replace every ``{{metric:ID}}``/
    ``{{special:ID}}`` placeholder with the Canonical Profile's own value — never with
    anything the LLM said. An unknown id is a hard failure, not a silent drop
    (`InvalidReportSection`, retried once by the caller)."""
    index = build_metric_display_value_index(profile)
    special_index = build_special_claim_index(profile)

    def _replace(match: re.Match[str]) -> str:
        namespace, identifier = match.group(1), match.group(2)
        source = index if namespace == "metric" else special_index
        if identifier not in source:
            raise InvalidReportSection(
                f"Unknown {namespace} id referenced by placeholder: {identifier!r}"
            )
        return source[identifier]

    return _PLACEHOLDER_PATTERN.sub(_replace, text)


def _generic_metric_block(profile: CanonicalProfile, metric_id: str) -> ContextBlock | None:
    index = build_metric_display_value_index(profile)
    if metric_id not in index:
        return None
    return ContextBlock(
        role="profile_fact", label=metric_id, content=f"{metric_id} = {index[metric_id]}"
    )


def _uniform_metric_grounding(
    profile: CanonicalProfile, knowledge: KnowledgeBase, metric_id: str
) -> tuple[ContextBlock, ...]:
    """Reuse Phase 3's composed German text for the eight uniform core metrics and the
    three timing metrics (personal_year/month/day) — both are `CalculationMetric`
    instances `compose_section` already knows how to ground with a display_value +
    knowledge themes/shadows, unlike the bare `_generic_metric_block` fallback below.

    Before this, a `timing`-section metric_id fell through to `_generic_metric_block`
    only (a bare "personal_year = 5" fact, no knowledge text) because this function
    checked `CORE_METRIC_IDS` alone. With the `timing` section otherwise carrying
    almost no substantive grounding of its own, a real provider's generation for it
    would lean on the much richer `previous_sections_summary` context from the prior
    (Pinnacles/Challenges) section instead — the root cause of the V1.6 C
    timing-report production bug this fixes."""
    if metric_id in CORE_METRIC_IDS:
        metric: CalculationMetric = getattr(profile.core_numbers, metric_id)
    elif metric_id in TIMING_METRIC_IDS:
        metric = getattr(profile.timing, metric_id)
    else:
        return ()
    section = compose_section(metric_id, metric, knowledge)
    return (ContextBlock(role="knowledge", label=metric_id, content=section.text_de),)


def _special_numbers_blocks(profile: CanonicalProfile) -> tuple[ContextBlock, ...]:
    core = profile.core_numbers
    return (
        ContextBlock(
            role="profile_fact",
            label="hidden_passion",
            content=f"Hidden Passion: values={list(core.hidden_passion.values)}, "
            f"frequency={core.hidden_passion.frequency}",
        ),
        ContextBlock(
            role="profile_fact",
            label="karmic_lessons",
            content=f"Karmic Lessons: {list(core.karmic_lessons.values)}",
        ),
        ContextBlock(
            role="profile_fact",
            label="subconscious_self",
            content=f"Subconscious Self: {core.subconscious_self.value}",
        ),
    )


def _cycles_blocks(profile: CanonicalProfile) -> tuple[ContextBlock, ...]:
    pinnacles = profile.cycles.pinnacles
    challenges = profile.cycles.challenges
    return (
        ContextBlock(
            role="profile_fact",
            label="pinnacles",
            content=(
                f"Pinnacle 1={pinnacles.pinnacle_1.display_value}, "
                f"Pinnacle 2={pinnacles.pinnacle_2.display_value}, "
                f"Pinnacle 3={pinnacles.pinnacle_3.display_value}, "
                f"Pinnacle 4={pinnacles.pinnacle_4.display_value}"
            ),
        ),
        ContextBlock(
            role="profile_fact",
            label="challenges",
            content=(
                f"Challenge 1={challenges.challenge_1}, Challenge 2={challenges.challenge_2}, "
                f"Challenge 3={challenges.challenge_3}, Challenge 4={challenges.challenge_4}"
            ),
        ),
    )


def _gather_context_blocks(
    profile: CanonicalProfile, knowledge: KnowledgeBase, spec: ReportSectionSpec
) -> tuple[ContextBlock, ...]:
    blocks: list[ContextBlock] = []

    for metric_id in spec.metric_refs:
        blocks.extend(_uniform_metric_grounding(profile, knowledge, metric_id))
        generic = _generic_metric_block(profile, metric_id)
        if generic is not None and not any(b.label == metric_id for b in blocks):
            blocks.append(generic)

    if spec.section_id == "special_numbers":
        blocks.extend(_special_numbers_blocks(profile))
    elif spec.section_id == "cycles":
        blocks.extend(_cycles_blocks(profile))
    elif spec.section_id in ("development", "calculation_appendix", "executive_profile"):
        # These sections synthesize across the whole profile rather than one metric;
        # ground them in the same core-metric summaries their siblings already have.
        for metric_id in CORE_METRIC_IDS:
            generic = _generic_metric_block(profile, metric_id)
            if generic is not None:
                blocks.append(generic)

    return tuple(blocks)


def _numeric_claims_for_spec(
    profile: CanonicalProfile, spec: ReportSectionSpec
) -> tuple[NumericClaim, ...]:
    index = build_metric_display_value_index(profile)
    metric_ids = spec.metric_refs or tuple(index.keys())[:3]
    return tuple(
        NumericClaim(metric_id=metric_id, display_value=index[metric_id])
        for metric_id in metric_ids
        if metric_id in index
    )


async def _generate_section(
    *,
    profile: CanonicalProfile,
    knowledge: KnowledgeBase,
    spec: ReportSectionSpec,
    llm: LLMProviderProtocol,
    global_summaries: tuple[str, ...],
    attempt: int,
    is_mock_provider: bool,
    planned_focus: str | None,
) -> StructuredReportSection:
    context_blocks = list(_gather_context_blocks(profile, knowledge, spec))

    if global_summaries:
        context_blocks.append(
            ContextBlock(
                role="instruction_supplement",
                label="previous_sections_summary",
                content=" | ".join(global_summaries),
            )
        )

    if planned_focus:
        context_blocks.append(
            ContextBlock(
                role="instruction_supplement", label="outline_focus", content=planned_focus
            )
        )

    # Real prompt text, not just request metadata: a concrete provider (ollama_provider)
    # never puts `request.metadata` into the actual chat messages it sends, so a target
    # word count living only in `metadata` would never reach a real LLM's prompt at
    # all — this block is what makes the target length an instruction the model
    # actually sees.
    context_blocks.append(
        ContextBlock(
            role="instruction_supplement",
            label="word_count_target",
            content=(
                f"Target length for this section: approximately {spec.target_word_count} "
                "words. Do not pad with repetition to reach this length."
            ),
        )
    )

    # The system instructions say to reference facts via "a known metric id" /
    # "a known special id" but never state which ids are actually known — a model
    # left to infer plausible-sounding names from prose like "personality = 44/8"
    # can (and, live against Ollama Cloud's deepseek-v4-pro, did) invent a
    # near-miss like `personality_number` instead of the real `personality`,
    # which `_resolve_placeholders` then rejects outright. These two indices are
    # the exact ground truth `_resolve_placeholders` validates against, so listing
    # their keys here guarantees every id the model is told is "known" actually
    # resolves.
    # NOTE: deliberately does not spell out the literal "{{metric:ID}}" placeholder
    # syntax here (unlike this docstring) — MockLLMProvider's deterministic filler
    # seeds itself from every context_block's raw content, so a literal "{{...}}"
    # written into an instruction block could itself get echoed into the generated
    # text and then misfire the very placeholder resolver this block exists to keep
    # accurate. Naming the two namespaces without the braces is safe either way.
    valid_metric_ids = sorted(build_metric_display_value_index(profile))
    valid_special_ids = sorted(build_special_claim_index(profile))
    context_blocks.append(
        ContextBlock(
            role="instruction_supplement",
            label="valid_placeholder_ids",
            content=(
                "The only valid ids in the metric placeholder namespace are: "
                f"{', '.join(valid_metric_ids)}. "
                "The only valid ids in the special placeholder namespace are: "
                f"{', '.join(valid_special_ids)}. "
                "Never invent an id outside these two lists, even if it seems descriptive."
            ),
        )
    )

    numeric_claims = _numeric_claims_for_spec(profile, spec)

    # `request.numeric_claims` (built below) is never turned into chat messages by any
    # concrete provider — ollama_provider._build_messages/_build_structured_messages only
    # read system_instructions/context_blocks/user_instructions — so the model was told
    # which metric ids EXIST (via valid_placeholder_ids above) but never which ones its own
    # `numeric_claims` output array is REQUIRED to cover for this specific section. Every
    # real generation since 388bbbb ("V1.6 C") consequently failed post-generation with
    # `InvalidReportSection: MissingMetricCoverage` from validate_metric_ref_coverage below,
    # because a model with no explicit instruction reasonably left the array empty or
    # partial. This block makes the requirement an instruction the model actually sees,
    # using the same canonical display values already given via the metric context blocks.
    if numeric_claims:
        required_ids = ", ".join(claim.metric_id for claim in numeric_claims)
        context_blocks.append(
            ContextBlock(
                role="instruction_supplement",
                label="required_numeric_claims",
                content=(
                    "numeric_claims must include exactly one entry per metric id: "
                    f"{required_ids}, each with the canonical display_value already given "
                    "above as a literal value (e.g. '22/4'), never the metric-placeholder "
                    "syntax used in the text field and never blank."
                ),
            )
        )

    if is_mock_provider:
        # Deterministic, network-free filler so MockLLMProvider-driven tests can
        # exercise realistic section lengths (including ULTIMATE-scale, 15,000+ words)
        # without a real model. Never sent to a real provider — see the module
        # docstring and the `is_mock_provider` branch this guards: injecting synthetic
        # filler text into a *real* LLM's prompt would just be prompt noise a real
        # model has no reason to reproduce, and risks being echoed back verbatim.
        overhead_words = len(f"[system] {_SYSTEM_INSTRUCTIONS}".split())
        overhead_words += sum(
            len(f"[{b.role}:{b.label}] {b.content}".split()) for b in context_blocks
        )
        overhead_words += 3 * len(numeric_claims)

        # Always lead with the section's own id/title so sections whose grounding
        # facts happen to overlap (e.g. executive_profile/development/
        # calculation_appendix all cite the same core metrics) still produce distinct
        # elaboration text — otherwise the global lint's DuplicateParagraphDetection
        # would (correctly) flag genuinely identical output.
        seed_phrases = (spec.section_id, spec.title) + tuple(
            block.content for block in context_blocks
        )
        elaboration_target = max(5, spec.target_word_count - overhead_words)
        elaboration = deterministic_elaboration(seed_phrases, elaboration_target)
        context_blocks.append(
            ContextBlock(
                role="instruction_supplement", label="elaboration_seed", content=elaboration
            )
        )

    request = StructuredGenerationRequest(
        system_instructions=_SYSTEM_INSTRUCTIONS,
        context_blocks=tuple(context_blocks),
        numeric_claims=numeric_claims,
        metadata={
            "section_id": spec.section_id,
            "target_word_count": str(spec.target_word_count),
            "attempt": str(attempt),
        },
        target_schema_name="GeneratedSectionContent",
    )

    result = await llm.generate_structured(request, GeneratedSectionContent)
    assert isinstance(result, GeneratedSectionContent)

    validate_numeric_claims(result.numeric_claims, profile)
    validate_metric_ref_coverage(
        result.numeric_claims,
        tuple(claim.metric_id for claim in numeric_claims),
        section_id=spec.section_id,
    )

    # template_text (still carrying {{metric:ID}}/{{special:ID}} placeholders) is
    # linted BEFORE placeholder resolution — the unauthorized-literal check only means
    # anything against the model's own raw wording, not against the profile's own
    # values that resolution will substitute in. Mock output is exempt: MockLLMProvider
    # deliberately echoes raw grounding facts (including bare digits) as part of how it
    # fabricates deterministic content, which is not "the model inventing a claim".
    template_text = result.text
    if not is_mock_provider:
        unauthorized = find_unauthorized_numeric_literals(template_text, profile)
        if unauthorized:
            raise InvalidReportSection(
                f"UnauthorizedNumericLiteral: section {spec.section_id!r} contains bare "
                f"digit(s) {unauthorized!r} not referenced via a metric/special placeholder"
            )

    text = _resolve_placeholders(template_text, profile)
    word_count = len(text.split())

    return StructuredReportSection(
        section_id=spec.section_id,
        title=spec.title,
        order_index=spec.order_index,
        text=text,
        word_count=word_count,
        summary=result.summary or f"{spec.title}: {word_count} words generated.",
        metric_refs=spec.metric_refs,
        knowledge_refs=spec.knowledge_refs,
    )


async def _generate_outline(
    *,
    profile: CanonicalProfile,
    manifest: ReportManifest,
    llm: LLMProviderProtocol,
) -> ReportOutline:
    """The AgentWrite planning step (master prompt §102-ish): one upfront structured
    call asking for a short planned focus per section, run only for the longer report
    types (`_OUTLINE_REPORT_TYPES`) where a QUICK report's own section list isn't
    already the outline. Grounded in every core metric so the plan can reference real
    facts; never asked to state a numeric value itself (`_OUTLINE_SYSTEM_INSTRUCTIONS`)
    — the outline's job is structure, not content, so it carries no numeric-claim
    surface of its own to validate."""
    context_blocks = [
        ContextBlock(
            role="instruction_supplement",
            label="sections",
            content=", ".join(f"{spec.section_id} ({spec.title})" for spec in manifest.sections),
        )
    ]
    for metric_id in CORE_METRIC_IDS:
        block = _generic_metric_block(profile, metric_id)
        if block is not None:
            context_blocks.append(block)

    request = StructuredGenerationRequest(
        system_instructions=_OUTLINE_SYSTEM_INSTRUCTIONS,
        context_blocks=tuple(context_blocks),
        target_schema_name="ReportOutline",
    )
    outline = await llm.generate_structured(request, ReportOutline)
    assert isinstance(outline, ReportOutline)
    known_section_ids = {spec.section_id for spec in manifest.sections}
    return ReportOutline(
        entries=tuple(entry for entry in outline.entries if entry.section_id in known_section_ids)
    )


async def generate_report(
    *,
    profile: CanonicalProfile,
    knowledge: KnowledgeBase,
    manifest: ReportManifest,
    llm: LLMProviderProtocol,
) -> StructuredReport:
    """Run the full AgentWrite pipeline. Raises ReportGenerationError if the assembled
    report fails the global lint even after the one permitted per-section repair."""
    health = await llm.health()
    if health.status in ("unavailable", "disabled"):
        raise ReportGenerationError(f"LLM_UNAVAILABLE: provider={health.provider}")
    is_mock_provider = health.provider == "mock"

    outline_by_section: dict[str, str] = {}
    if manifest.report_type in _OUTLINE_REPORT_TYPES:
        outline = await _generate_outline(profile=profile, manifest=manifest, llm=llm)
        outline_by_section = {
            entry.section_id: entry.planned_focus
            for entry in outline.entries
            if entry.planned_focus
        }

    sections: list[StructuredReportSection] = []
    summaries: list[str] = []

    for spec in manifest.sections:
        planned_focus = outline_by_section.get(spec.section_id)
        try:
            section = await _generate_section(
                profile=profile,
                knowledge=knowledge,
                spec=spec,
                llm=llm,
                global_summaries=tuple(summaries),
                attempt=1,
                is_mock_provider=is_mock_provider,
                planned_focus=planned_focus,
            )
        except InvalidReportSection:
            # One controlled repair attempt (master prompt §100) — regenerate once.
            section = await _generate_section(
                profile=profile,
                knowledge=knowledge,
                spec=spec,
                llm=llm,
                global_summaries=tuple(summaries),
                attempt=2,
                is_mock_provider=is_mock_provider,
                planned_focus=planned_focus,
            )
        sections.append(section)
        summaries.append(section.summary)

    structured_sections = tuple(sections)
    lint_result = lint_report(manifest, structured_sections, profile)
    if not lint_result.is_valid:
        raise ReportGenerationError("REPORT_VALIDATION_FAILED: " + "; ".join(lint_result.errors))

    provider_health = await llm.health()
    return StructuredReport(
        report_type=manifest.report_type,
        language=manifest.language,
        calculation_id=manifest.calculation_id,
        calculation_version=profile.calculation_version,
        knowledge_version=knowledge.manifest.version,
        prompt_version=manifest.prompt_version,
        model_provider=provider_health.provider,
        model_name="mock-v1" if provider_health.provider == "mock" else provider_health.provider,
        sections=structured_sections,
        total_word_count=sum(s.word_count for s in structured_sections),
    )
