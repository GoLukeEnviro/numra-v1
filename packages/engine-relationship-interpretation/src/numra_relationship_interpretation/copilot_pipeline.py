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
from numra_interpretation.llm.types import LLMProvider as LLMProviderProtocol
from numra_interpretation.llm.types import NumericClaim, StructuredGenerationRequest
from numra_interpretation.llm.validator import validate_numeric_claims
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
    reply: _CopilotGeneratedReply, *, grounding_profiles: tuple[CanonicalProfile, ...]
) -> None:
    if reply.basis_type not in VALID_BASIS_TYPES:
        raise AnalysisGenerationError(
            f"INVALID_BASIS_TYPE: {reply.basis_type!r} is not one of {sorted(VALID_BASIS_TYPES)}"
        )
    _validate_claims_against_profiles(reply.numeric_claims, grounding_profiles)


async def _generate_once(
    *, request: StructuredGenerationRequest, llm: LLMProviderProtocol
) -> _CopilotGeneratedReply:
    result = await llm.generate_structured(request, _CopilotGeneratedReply)
    assert isinstance(result, _CopilotGeneratedReply)
    return result


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
    try:
        reply = await _generate_once(request=request, llm=llm)
        _validate_reply(reply, grounding_profiles=grounding_profiles)
    except (AnalysisGenerationError, InvalidReportSection) as exc:
        try:
            reply = await _generate_once(request=request, llm=llm)
            _validate_reply(reply, grounding_profiles=grounding_profiles)
        except (AnalysisGenerationError, InvalidReportSection) as retry_exc:
            raise AnalysisGenerationError(
                f"COPILOT_REPLY_VALIDATION_FAILED: failed twice: first={exc}; retry={retry_exc}"
            ) from retry_exc

    health = await llm.health()
    return CopilotReplyResult(
        text=reply.text,
        basis_type=reply.basis_type,
        numeric_claims=reply.numeric_claims,
        model_provider=health.provider,
        model_name="mock-v1" if health.provider == "mock" else health.provider,
    )
