"""#174 (part 2): the repair attempt must be a *corrective* retry.

The measured defect: a grounding rejection (e.g. the model claims `22/4` where the
canonical value is `9`) was retried with the byte-identical request, so a
deterministic-style hallucination burned both attempts and the turn ended FAILED
with empty content. These tests pin the corrective behaviour:

1. the retry's request names the canonical values the guard flagged,
2. the retry's request is demonstrably different from the first attempt,
3. the guard itself is untouched — a reply that stays wrong is still rejected,
4. the first attempt is never weakened (it is still sent as-is).
"""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import BaseModel

from numra_interpretation.llm.types import (
    ContextBlock,
    ProviderHealth,
    StructuredGenerationRequest,
)
from numra_numerology.engine import calculate_profile
from numra_numerology.models.person import PersonInput
from numra_relationship_interpretation.copilot_pipeline import generate_copilot_reply
from numra_relationship_interpretation.errors import AnalysisGenerationError

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def profile_self():
    person = PersonInput(
        birth_first_names="Anna",
        birth_middle_names=None,
        birth_last_name="Berger",
        birth_date=dt.date(1990, 3, 14),
    )
    return calculate_profile(person, as_of_date=dt.date(2026, 8, 19))


def _request() -> StructuredGenerationRequest:
    return StructuredGenerationRequest(
        system_instructions="sys",
        context_blocks=(ContextBlock(role="profile_fact", label="p", content="life_path=6"),),
        user_instructions="Was sagt mein Lebenspfad aus?",
        target_schema_name="CopilotGeneratedReply",
    )


class _RecordingProvider:
    """Records every request it receives so the test can compare attempt 1 and 2."""

    def __init__(self, replies: list[dict[str, object]]) -> None:
        self._replies = list(replies)
        self.requests: list[StructuredGenerationRequest] = []

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="healthy", provider="recording", checked_at=dt.datetime.now(dt.UTC)
        )

    async def generate(self, request):  # pragma: no cover - unused
        raise NotImplementedError

    async def generate_structured(
        self, request: StructuredGenerationRequest, schema: type[BaseModel]
    ) -> BaseModel:
        self.requests.append(request)
        payload = self._replies[min(len(self.requests) - 1, len(self._replies) - 1)]
        return schema.model_validate(payload)


@pytest.mark.asyncio
async def test_retry_request_carries_the_canonical_values_the_guard_flagged(profile_self) -> None:
    canonical = profile_self.core_numbers.life_path.display_value
    provider = _RecordingProvider(
        [
            {
                "text": "falsch",
                "basis_type": "NUMEROLOGY_MODEL",
                "numeric_claims": [{"metric_id": "life_path", "display_value": "22/4"}],
            },
            {
                "text": "richtig",
                "basis_type": "NUMEROLOGY_MODEL",
                "numeric_claims": [{"metric_id": "life_path", "display_value": canonical}],
            },
        ]
    )

    result = await generate_copilot_reply(
        request=_request(),
        llm=provider,
        knowledge_version="v1",
        grounding_profiles=(profile_self,),
    )

    assert result.text == "richtig"
    assert len(provider.requests) == 2
    retry = provider.requests[1]
    corrections = [
        block for block in retry.context_blocks if block.label == "canonical_value_correction"
    ]
    assert corrections, "the retry carries no correction block"
    correction = corrections[-1].content
    # The correction must name the metric and its authoritative value ...
    assert "life_path" in correction
    assert canonical in correction
    # ... and must not leak the rejected claim as if it were acceptable.
    assert "22/4" not in correction
    # It is advice to the model, carried as its own block, never merged into the
    # system instructions (which would give model output a trust level it must not have).
    assert corrections[-1].role == "instruction_supplement"


@pytest.mark.asyncio
async def test_retry_request_differs_from_the_first_attempt(profile_self) -> None:
    """Regression guard for the measured defect: identical prompts made the second
    attempt worthless against a deterministic hallucination."""
    provider = _RecordingProvider(
        [
            {
                "text": "falsch",
                "basis_type": "NUMEROLOGY_MODEL",
                "numeric_claims": [{"metric_id": "life_path", "display_value": "22/4"}],
            },
            {
                "text": "immer noch falsch",
                "basis_type": "NUMEROLOGY_MODEL",
                "numeric_claims": [{"metric_id": "life_path", "display_value": "22/4"}],
            },
        ]
    )

    with pytest.raises(AnalysisGenerationError):
        await generate_copilot_reply(
            request=_request(),
            llm=provider,
            knowledge_version="v1",
            grounding_profiles=(profile_self,),
        )

    first, second = provider.requests
    assert (first.user_instructions, first.context_blocks) != (
        second.user_instructions,
        second.context_blocks,
    )


@pytest.mark.asyncio
async def test_guard_still_rejects_a_reply_that_stays_wrong(profile_self) -> None:
    """The correction is advice, not a weakening: a reply that ignores it is rejected."""
    provider = _RecordingProvider(
        [
            {
                "text": "falsch",
                "basis_type": "NUMEROLOGY_MODEL",
                "numeric_claims": [{"metric_id": "life_path", "display_value": "22/4"}],
            },
            {
                "text": "weiter falsch",
                "basis_type": "NUMEROLOGY_MODEL",
                "numeric_claims": [{"metric_id": "life_path", "display_value": "22/4"}],
            },
        ]
    )

    with pytest.raises(AnalysisGenerationError) as excinfo:
        await generate_copilot_reply(
            request=_request(),
            llm=provider,
            knowledge_version="v1",
            grounding_profiles=(profile_self,),
        )

    assert "COPILOT_REPLY_VALIDATION_FAILED" in str(excinfo.value)
    assert len(provider.requests) == 2  # exactly one repair attempt, as before


@pytest.mark.asyncio
async def test_first_attempt_request_is_unmodified(profile_self) -> None:
    """No correction context on the first call — it is only added after a rejection."""
    provider = _RecordingProvider(
        [
            {
                "text": "richtig",
                "basis_type": "NUMEROLOGY_MODEL",
                "numeric_claims": [
                    {
                        "metric_id": "life_path",
                        "display_value": profile_self.core_numbers.life_path.display_value,
                    }
                ],
            }
        ]
    )

    await generate_copilot_reply(
        request=_request(),
        llm=provider,
        knowledge_version="v1",
        grounding_profiles=(profile_self,),
    )

    assert len(provider.requests) == 1
    assert provider.requests[0] == _request()
