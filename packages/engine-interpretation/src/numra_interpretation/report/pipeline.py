"""The AgentWrite pipeline (numra-report-v3): Canonical Profile + Knowledge +
Report Manifest -> per-section structured generation -> placeholder coverage ->
assembly -> global lint -> `StructuredReport`.

No calculation happens here. Numeric facts in prose are `{{metric:ID}}` /
`{{special:ID}}` placeholders resolved from the Canonical Profile after generation.
The model returns only `text` and `summary`; claims are built from the manifest.
"""

from __future__ import annotations

import re

from numra_interpretation.composer import (
    CORE_METRIC_IDS,
    TIMING_METRIC_IDS,
    compose_extended_sections,
    compose_section,
)
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
    extract_placeholder_metric_ids,
    extract_special_placeholder_ids,
    find_unauthorized_numeric_literals,
    validate_placeholder_coverage,
)
from numra_interpretation.report.content_padding import deterministic_elaboration
from numra_interpretation.report.linter import lint_report
from numra_interpretation.report.manifest import ReportManifest, ReportSectionSpec
from numra_interpretation.report.prompts import (
    OUTLINE_SYSTEM,
    SYSTEM_INSTRUCTIONS,
    render_outline_user,
    render_section_user,
)
from numra_interpretation.report.schemas import (
    GeneratedSectionContent,
    ReportOutline,
    StructuredReport,
    StructuredReportSection,
)
from numra_numerology.models.metric import CalculationMetric
from numra_numerology.models.profile import CanonicalProfile

__all__ = ["ReportGenerationError", "generate_report"]

_OUTLINE_REPORT_TYPES = ("FULL", "ULTIMATE")

_PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*(metric|special)\s*:\s*([a-zA-Z0-9_]+)\s*\}")

_SPECIAL_SECTION_IDS = frozenset({"hidden_passion", "karmic_lessons", "subconscious_self"})
_CYCLE_SECTION_IDS = frozenset(
    {
        "pinnacle_1",
        "pinnacle_2",
        "pinnacle_3",
        "pinnacle_4",
        "challenge_1",
        "challenge_2",
        "challenge_3",
        "challenge_4",
    }
)


class ReportGenerationError(Exception):
    """Raised when the pipeline cannot produce a REPORT_STATUS=VALID report, even after
    the one permitted repair attempt.
    """


def _resolve_placeholders(text: str, profile: CanonicalProfile) -> str:
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


def _word_band(target: int) -> tuple[int, int]:
    """Instruction band around the manifest target. Prefer shorter over padding."""
    low = max(80, int(target * 0.7))
    high = max(low + 1, int(target * 1.15))
    return low, high


def _placeholder_for(metric_id: str) -> str:
    if metric_id in ("hidden_passion", "karmic_lessons"):
        return f"{{{{special:{metric_id}}}}}"
    return f"{{{{metric:{metric_id}}}}}"


def _required_placeholder_ids(spec: ReportSectionSpec) -> tuple[str, ...]:
    if spec.metric_refs:
        return spec.metric_refs
    if spec.section_id == "special_numbers":
        return ("hidden_passion", "karmic_lessons", "subconscious_self")
    if spec.section_id == "cycles":
        return (
            "pinnacle_1",
            "pinnacle_2",
            "pinnacle_3",
            "pinnacle_4",
            "challenge_1",
            "challenge_2",
            "challenge_3",
            "challenge_4",
        )
    if spec.section_id in ("executive_profile", "development", "calculation_appendix"):
        return ("life_path", "expression", "soul_urge")
    return ()


def _claims_from_manifest(
    profile: CanonicalProfile, spec: ReportSectionSpec
) -> tuple[NumericClaim, ...]:
    """Pipeline-owned claims — never taken from model output."""
    index = build_metric_display_value_index(profile)
    special_index = build_special_claim_index(profile)
    claims: list[NumericClaim] = []
    for metric_id in _required_placeholder_ids(spec):
        if metric_id in index:
            claims.append(NumericClaim(metric_id=metric_id, display_value=index[metric_id]))
        elif metric_id in special_index:
            claims.append(NumericClaim(metric_id=metric_id, display_value=special_index[metric_id]))
    return tuple(claims)


def _extended_by_id(profile: CanonicalProfile, knowledge: KnowledgeBase) -> dict[str, str]:
    return {section.metric_id: section.text_de for section in compose_extended_sections(profile, knowledge)}


def _knowledge_for_spec(
    profile: CanonicalProfile,
    knowledge: KnowledgeBase,
    spec: ReportSectionSpec,
    extended: dict[str, str],
) -> str:
    parts: list[str] = []
    for metric_id in spec.metric_refs:
        if metric_id in CORE_METRIC_IDS:
            metric: CalculationMetric = getattr(profile.core_numbers, metric_id)
            parts.append(compose_section(metric_id, metric, knowledge).text_de)
        elif metric_id in TIMING_METRIC_IDS:
            metric = getattr(profile.timing, metric_id)
            parts.append(compose_section(metric_id, metric, knowledge).text_de)
        elif metric_id in extended:
            parts.append(extended[metric_id])
    if spec.section_id == "special_numbers":
        for metric_id in ("hidden_passion", "karmic_lessons", "subconscious_self"):
            if metric_id in extended:
                parts.append(extended[metric_id])
    elif spec.section_id == "cycles":
        for metric_id in (
            "pinnacle_1",
            "pinnacle_2",
            "pinnacle_3",
            "pinnacle_4",
            "challenge_1",
            "challenge_2",
            "challenge_3",
            "challenge_4",
        ):
            if metric_id in extended:
                parts.append(extended[metric_id])
    elif spec.section_id in ("development", "calculation_appendix", "executive_profile"):
        for metric_id in CORE_METRIC_IDS:
            metric = getattr(profile.core_numbers, metric_id)
            parts.append(compose_section(metric_id, metric, knowledge).text_de)
    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        if part not in seen:
            seen.add(part)
            unique.append(part)
    return "\n\n".join(unique)


def _profile_facts_for_spec(spec: ReportSectionSpec) -> str:
    """Facts as placeholder citations so the model sees the syntax, not raw digits."""
    ids = _required_placeholder_ids(spec)
    if not ids:
        return "(keine Pflichtfakten in diesem Abschnitt)"
    return "\n".join(f"- {metric_id} = {_placeholder_for(metric_id)}" for metric_id in ids)


def _theme_bullets(profile: CanonicalProfile, knowledge: KnowledgeBase) -> str:
    bullets: list[str] = []
    for metric_id in CORE_METRIC_IDS:
        metric = getattr(profile.core_numbers, metric_id)
        section = compose_section(metric_id, metric, knowledge)
        themes = ", ".join(section.core_themes[:3])
        bullets.append(f"- {section.display_name_de}: {themes}")
    return "\n".join(bullets)


def _prior_summary_text(summaries: tuple[str, ...]) -> str:
    if not summaries:
        return "Noch nichts gesagt."
    last = summaries[-1].strip()
    return f"Zuletzt: {last}\nNicht nochmal dieselben Sätze öffnen. Hier nur diesen Abschnitt vertiefen."


def _repair_block(error: str, valid_metric_ids: str, valid_special_ids: str) -> str:
    return (
        f"Vorheriger Entwurf wurde abgelehnt: {error}\n"
        "Schreibe text neu. Keine Literalziffern für Numerologiewerte.\n"
        f"Gültige metric-IDs: {valid_metric_ids}\n"
        f"Gültige special-IDs: {valid_special_ids}"
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
    extended: dict[str, str],
    repair_error: str | None,
) -> StructuredReportSection:
    valid_metric_ids = ", ".join(sorted(build_metric_display_value_index(profile)))
    valid_special_ids = ", ".join(sorted(build_special_claim_index(profile)))
    required_ids = _required_placeholder_ids(spec)
    required_placeholders = "\n".join(_placeholder_for(metric_id) for metric_id in required_ids)
    min_words, max_words = _word_band(spec.target_word_count)
    knowledge_text = _knowledge_for_spec(profile, knowledge, spec, extended)
    repair = (
        _repair_block(repair_error, valid_metric_ids, valid_special_ids) if repair_error else ""
    )
    user_instructions = render_section_user(
        language=knowledge.manifest.language if hasattr(knowledge.manifest, "language") else "de",
        section_title=spec.title,
        section_id=spec.section_id,
        min_words=min_words,
        max_words=max_words,
        planned_focus=planned_focus or "",
        required_placeholders=required_placeholders,
        valid_metric_ids=valid_metric_ids,
        valid_special_ids=valid_special_ids,
        profile_facts=_profile_facts_for_spec(spec),
        knowledge_text=knowledge_text,
        prior_summary=_prior_summary_text(global_summaries),
        repair_block=repair,
    )

    context_blocks: list[ContextBlock] = [
        ContextBlock(role="knowledge", label=spec.section_id, content=knowledge_text or spec.title),
    ]
    if is_mock_provider:
        seed_phrases = (spec.section_id, spec.title, user_instructions, knowledge_text)
        elaboration = deterministic_elaboration(seed_phrases, max(5, spec.target_word_count))
        context_blocks.append(
            ContextBlock(role="instruction_supplement", label="elaboration_seed", content=elaboration)
        )

    numeric_claims = _claims_from_manifest(profile, spec)
    request = StructuredGenerationRequest(
        system_instructions=SYSTEM_INSTRUCTIONS,
        context_blocks=tuple(context_blocks),
        user_instructions=user_instructions,
        numeric_claims=numeric_claims,
        metadata={
            "section_id": spec.section_id,
            "target_word_count": str(spec.target_word_count),
            "attempt": str(attempt),
            "prompt_version": "numra-report-v3",
        },
        target_schema_name="GeneratedSectionContent",
    )

    result = await llm.generate_structured(request, GeneratedSectionContent)
    assert isinstance(result, GeneratedSectionContent)

    template_text = result.text
    if not is_mock_provider:
        unauthorized = find_unauthorized_numeric_literals(template_text, profile)
        if unauthorized:
            raise InvalidReportSection(
                f"UnauthorizedNumericLiteral: section {spec.section_id!r} contains bare "
                f"digit(s) {unauthorized!r} not referenced via a metric/special placeholder"
            )

    validate_placeholder_coverage(
        template_text,
        required_ids,
        section_id=spec.section_id,
    )

    text = _resolve_placeholders(template_text, profile)
    word_count = len(text.split())

    return StructuredReportSection(
        section_id=spec.section_id,
        title=spec.title,
        order_index=spec.order_index,
        text=text,
        word_count=word_count,
        summary=result.summary or f"{spec.title}: {word_count} Wörter.",
        metric_refs=spec.metric_refs,
        knowledge_refs=spec.knowledge_refs,
    )


async def _generate_outline(
    *,
    profile: CanonicalProfile,
    knowledge: KnowledgeBase,
    manifest: ReportManifest,
    llm: LLMProviderProtocol,
) -> ReportOutline:
    section_list = ", ".join(f"{spec.section_id} ({spec.title})" for spec in manifest.sections)
    user_instructions = render_outline_user(
        section_list=section_list,
        theme_bullets=_theme_bullets(profile, knowledge),
    )
    request = StructuredGenerationRequest(
        system_instructions=OUTLINE_SYSTEM,
        context_blocks=(),
        user_instructions=user_instructions,
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
    health = await llm.health()
    if health.status in ("unavailable", "disabled"):
        raise ReportGenerationError(f"LLM_UNAVAILABLE: provider={health.provider}")
    is_mock_provider = health.provider == "mock"
    extended = _extended_by_id(profile, knowledge)

    outline_by_section: dict[str, str] = {}
    if manifest.report_type in _OUTLINE_REPORT_TYPES:
        outline = await _generate_outline(
            profile=profile, knowledge=knowledge, manifest=manifest, llm=llm
        )
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
                extended=extended,
                repair_error=None,
            )
        except InvalidReportSection as exc:
            section = await _generate_section(
                profile=profile,
                knowledge=knowledge,
                spec=spec,
                llm=llm,
                global_summaries=tuple(summaries),
                attempt=2,
                is_mock_provider=is_mock_provider,
                planned_focus=planned_focus,
                extended=extended,
                repair_error=str(exc),
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
