"""Synchronous single-call generation for Copilot chat replies (PR-V2-09).

Deliberately NOT job/worker-based, unlike `pipeline.generate_relationship_analysis`/
`generate_shadow_dynamics` -- a chat reply needs interactive latency
(specs/v2/copilot-grounding-spec.md), so the caller (`numra_api.services.
copilot_service`) awaits this directly inside the request/response cycle.

No calculation happens here, and this module never assembles context itself -- the
caller already built the closed `StructuredGenerationRequest` (via
`numra_api.services.copilot_context_builder`) before calling in; this module's only
job is the render -> validate -> one-repair-attempt loop, mirroring
`pipeline.py`'s existing discipline for relationship/shadow-dynamics generation
(docs/adr/011-v2-llm-grounding.md: an explicit `ContextBuilder` step the LLM itself
never performs).

Truth classification: every reply must self-report a `basis_type` from the fixed set
in `copilot-grounding-spec.md` ("Truth classification") -- validated here, never
trusted at face value. `INSUFFICIENT_EVIDENCE` is treated as a normal, valid, and
frequently correct result, not a failure.

Numeric-claim grounding: reuses `numra_interpretation.llm.validator.
validate_numeric_claims` (not reinvented) against every `CanonicalProfile` the caller
says grounded this request -- a claim must match at least one of them exactly, or the
whole reply is rejected/retried, never silently corrected.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from numra_interpretation.errors import InvalidReportSection
from numra_interpretation.llm.rendering_guard import contains_prompt_scaffolding
from numra_interpretation.llm.types import ContextBlock, NumericClaim, StructuredGenerationRequest
from numra_interpretation.llm.types import LLMProvider as LLMProviderProtocol
from numra_interpretation.llm.validator import (
    build_metric_display_value_index,
    build_special_claim_index,
    validate_numeric_claims,
)
from numra_interpretation.report.evidence_linter import lint_free_text_for_causal_language
from numra_numerology.models.profile import CanonicalProfile
from numra_relationship_interpretation.errors import AnalysisGenerationError

__all__ = ["CopilotReplyResult", "generate_copilot_reply"]

#: Bumped whenever the Copilot prompt shape/instructions change materially --
#: snapshotted onto every persisted `ChatMessage` (mirrors `pipeline.PROMPT_VERSION`).
COPILOT_PROMPT_VERSION = "numra-copilot-v1"

#: The exact, closed set from specs/v2/copilot-grounding-spec.md "Truth
#: classification" -- any other value is a validation failure, not silently accepted.
VALID_BASIS_TYPES: frozenset[str] = frozenset(
    {"NUMEROLOGY_MODEL", "OBSERVED_WORKSPACE_DATA", "MIXED", "INSUFFICIENT_EVIDENCE"}
)


class _CopilotGeneratedReply(BaseModel):
    """Structured-generation target. ``basis_type`` defaults to
    ``INSUFFICIENT_EVIDENCE`` only so `numra_interpretation.llm.mock_provider.
    MockLLMProvider` (which never invents a value for a field it doesn't recognize)
    can still construct this schema deterministically in tests -- a real provider is
    always expected to fill it explicitly; `_validate_reply` below re-checks it
    regardless of provenance."""

    model_config = ConfigDict(frozen=True)

    text: str
    basis_type: str = "INSUFFICIENT_EVIDENCE"
    numeric_claims: tuple[NumericClaim, ...] = ()


class CopilotReplyResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    basis_type: str
    numeric_claims: tuple[NumericClaim, ...] = ()
    model_provider: str
    model_name: str


def _validate_claims_against_profiles(
    claims: tuple[NumericClaim, ...], profiles: tuple[CanonicalProfile, ...]
) -> None:
    """A claim is accepted if it matches *any* of the grounding profiles exactly
    (reuses `validate_numeric_claims` per profile, unmodified) -- rejected only if it
    matches none. Empty `claims` is always valid (a reply need not cite a number)."""
    if not claims:
        return
    last_error: Exception | None = None
    for profile in profiles:
        try:
            validate_numeric_claims(claims, profile)
            return
        except InvalidReportSection as exc:
            last_error = exc
    raise AnalysisGenerationError(
        f"NUMERIC_CLAIM_VALIDATION_FAILED: no grounding profile matched: {last_error}"
    )


def _validate_reply(
    reply: _CopilotGeneratedReply,
    *,
    grounding_profiles: tuple[CanonicalProfile, ...],
    is_mock_provider: bool,
) -> None:
    # Die Scaffolding-Pruefung war hier bisher die einzige Ausnahme im ganzen
    # LLM-Pfad: die Copilot-Antwort verliess sich darauf, dass der Provider sich selbst
    # als "mock" meldet, und ein Provider, der seine Anfrage zurueckgibt, ohne das zu
    # tun (Wrapper, kuenftiger Provider, Mock-Unterklasse), haette seinen kompletten
    # Prompt als `ChatMessage.content` persistiert. Der Mock-Pfad bleibt ausgenommen --
    # er echot per Konstruktion und wird unten durch den festen, belegten Satz ersetzt,
    # nicht durch Ablehnung.
    if not is_mock_provider and contains_prompt_scaffolding(reply.text):
        raise AnalysisGenerationError(
            "PROMPT_SCAFFOLDING_REJECTED: reply carries request scaffolding instead of "
            "rendered text (never rendered or persisted)"
        )
    if reply.basis_type not in VALID_BASIS_TYPES:
        raise AnalysisGenerationError(
            f"INVALID_BASIS_TYPE: {reply.basis_type!r} is not one of {sorted(VALID_BASIS_TYPES)}"
        )
    _validate_claims_against_profiles(reply.numeric_claims, grounding_profiles)
    # PR-V2-11, specs/v2/evidence-policy.md "Correlation language": unbedingt, nicht
    # nur fuer OBSERVED_WORKSPACE_DATA/MIXED. Ein Modell kann kausal formulieren,
    # waehrend es sich selbst als NUMEROLOGY_MODEL deklariert -- die Klassifikation
    # wird hier ohnehin nie auf Wort genommen (siehe Modul-Docstring). Defense in
    # Depth neben dem strukturellen Linter in evidence_service.py.
    causal_lint = lint_free_text_for_causal_language(reply.text)
    if not causal_lint.is_valid:
        raise AnalysisGenerationError(f"CAUSAL_LANGUAGE_REJECTED: {'; '.join(causal_lint.errors)}")


async def _generate_once(
    *, request: StructuredGenerationRequest, llm: LLMProviderProtocol
) -> _CopilotGeneratedReply:
    result = await llm.generate_structured(request, _CopilotGeneratedReply)
    assert isinstance(result, _CopilotGeneratedReply)
    return result


def _metric_index(profile: CanonicalProfile) -> dict[str, str]:
    """Scalar and special metric ids merged, exactly as the validator sees them."""
    return {**build_metric_display_value_index(profile), **build_special_claim_index(profile)}


def _flagged_canonical_values(
    *, reply: _CopilotGeneratedReply, grounding_profiles: tuple[CanonicalProfile, ...]
) -> tuple[tuple[str, str, str], ...]:
    """(metric_id, claimed, canonical) for every numeric claim the guard rejects.

    A claim is flagged only when it matches *no* grounding profile — the same rule the
    validator applies — so a claim that is correct for some profile is never reported.
    """
    indexes = [_metric_index(profile) for profile in grounding_profiles]
    flagged: list[tuple[str, str, str]] = []
    for claim in reply.numeric_claims:
        if any(index.get(claim.metric_id) == claim.display_value for index in indexes):
            continue
        canonical = next(
            (index[claim.metric_id] for index in indexes if claim.metric_id in index), None
        )
        if canonical is not None:
            flagged.append((claim.metric_id, claim.display_value, canonical))
    return tuple(flagged)


def _corrective_request(
    *,
    request: StructuredGenerationRequest,
    flagged: tuple[tuple[str, str, str], ...],
) -> StructuredGenerationRequest:
    """A `request` whose *next* attempt is told which canonical values it must use.

    This is the difference between a repair attempt and a coin flip: the measured
    defect (#174) was that the retry repeated the byte-identical prompt, so a
    deterministic hallucination burned both attempts and the turn ended FAILED.

    The correction is added as its own `instruction_supplement` block — never merged
    into `system_instructions`, which would give model output a trust level it must
    not have — and it never restates the rejected value as acceptable.
    """
    lines = [
        "Your previous answer was rejected because it cited a number that does not "
        "match the canonical values. Use exactly these values:",
    ]
    lines.extend(f"- {metric_id}: {canonical}" for metric_id, _claimed, canonical in flagged)
    lines.append("Do not cite any other value for these metrics.")
    correction = ContextBlock(
        role="instruction_supplement",
        label="canonical_value_correction",
        content="\n".join(lines),
    )
    return request.model_copy(update={"context_blocks": (*request.context_blocks, correction)})


async def generate_copilot_reply(
    *,
    request: StructuredGenerationRequest,
    llm: LLMProviderProtocol,
    knowledge_version: str,  # noqa: ARG001 - snapshotted by the caller, not used to branch here
    grounding_profiles: tuple[CanonicalProfile, ...],
) -> CopilotReplyResult:
    """Render one Copilot reply. Raises `AnalysisGenerationError` if the reply still
    fails validation after one permitted repair attempt -- same one-repair-attempt
    discipline as `pipeline.generate_relationship_analysis`. The caller (
    `numra_api.services.copilot_service`) catches this and persists the ASSISTANT
    `ChatMessage` as FAILED, it never propagates as an uncaught 500."""
    # Die Provider-Identitaet steht vor der Validierung fest: die Scaffolding-Pruefung
    # haengt davon ab (siehe `_validate_reply`), und `health()` ist ein billiger,
    # provider-eigener Aufruf ohne Netzwerkzugriff.
    health = await llm.health()
    is_mock_provider = health.provider == "mock"

    try:
        reply = await _generate_once(request=request, llm=llm)
        _validate_reply(
            reply, grounding_profiles=grounding_profiles, is_mock_provider=is_mock_provider
        )
    except (AnalysisGenerationError, InvalidReportSection) as exc:
        # Ein echter Reparaturversuch: der zweite Aufruf bekommt die kanonischen Werte
        # der beanstandeten Metriken mit (#174). Der gemessene Defekt war, dass der
        # Retry den byte-identischen Prompt wiederholte und eine deterministische
        # Halluzination damit beide Versuche verbrannte. Wurde nichts Konkretes
        # beanstandet (z. B. Scaffolding-Fund ohne Zahlenbezug), bleibt der Prompt
        # unveraendert -- dann gibt es nichts zu korrigieren.
        flagged = _flagged_canonical_values(reply=reply, grounding_profiles=grounding_profiles)
        retry_request = (
            _corrective_request(request=request, flagged=flagged) if flagged else request
        )
        try:
            reply = await _generate_once(request=retry_request, llm=llm)
            _validate_reply(
                reply, grounding_profiles=grounding_profiles, is_mock_provider=is_mock_provider
            )
        except (AnalysisGenerationError, InvalidReportSection) as retry_exc:
            raise AnalysisGenerationError(
                f"COPILOT_REPLY_VALIDATION_FAILED: failed twice: first={exc}; retry={retry_exc}"
            ) from retry_exc

    text = reply.text
    if is_mock_provider:
        text = (
            "Für diese Frage gibt es in den freigegebenen Daten noch keine ausreichende Grundlage."
        )
    return CopilotReplyResult(
        text=text,
        basis_type=reply.basis_type,
        numeric_claims=reply.numeric_claims,
        model_provider=health.provider,
        model_name="mock-v1" if health.provider == "mock" else health.provider,
    )
