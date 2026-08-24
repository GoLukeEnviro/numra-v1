"""Structured request/result types and the `LLMProvider` protocol.

Prompt-injection containment principle (load-bearing for this whole module): a
`GenerationRequest` never lets a caller build a single opaque string that mixes system
instructions with user-supplied content. Instead the request is a set of separate,
role-tagged fields:

- ``system_instructions`` — fixed, developer-authored instruction text. Never contains
  interpolated user input.
- ``context_blocks`` — role-tagged, developer-assembled grounding data (profile facts,
  knowledge excerpts). Each block is a separate structured object, not a
  string-concatenated blob.
- ``user_instructions`` — the one field that may carry end-user-supplied text. It stays
  a distinct field all the way to the provider boundary; a concrete provider
  implementation (see `ollama_provider.py`) must pass it as its own message/role in the
  underlying API call, never splice it into ``system_instructions``.
- ``numeric_claims`` — the set of `{metric_id, display_value}` facts the generated
  content is expected to stay consistent with (see `validator.py`).

Nothing in this module makes network calls or imports an LLM SDK; it is pure typing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "ContextBlock",
    "GenerationRequest",
    "GenerationResult",
    "LLMProvider",
    "NumericClaim",
    "ProviderHealth",
    "StructuredGenerationRequest",
]


class ProviderHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    status: Literal["healthy", "degraded", "unavailable", "disabled"]
    provider: str
    checked_at: datetime
    detail: str | None = None


class NumericClaim(BaseModel):
    """A single explicit claim that generated content makes about a canonical metric
    value. Validated against the `CanonicalProfile` by `validator.validate_numeric_claims`
    — never trusted at face value."""

    model_config = ConfigDict(frozen=True)

    metric_id: str = Field(
        description="The known metric or special id this claim is about, e.g. 'life_path'."
    )
    display_value: str = Field(
        description=(
            "The literal, already-resolved canonical value for this metric, e.g. '22/4'. "
            "Never the '{{metric:ID}}' or '{{special:ID}}' placeholder syntax, and never "
            "an empty string — that placeholder syntax belongs only in the free-text "
            "content, not in this field."
        )
    )


class ContextBlock(BaseModel):
    """One role-tagged piece of developer-assembled grounding context.

    ``role`` distinguishes provenance so a provider adapter can decide how to present
    each block (e.g. as a separate system/tool message) without ever merging it into a
    single unstructured string alongside ``user_instructions``.
    """

    model_config = ConfigDict(frozen=True)

    role: Literal["profile_fact", "knowledge", "instruction_supplement"]
    label: str
    content: str


class GenerationRequest(BaseModel):
    """A structured generation request. See module docstring for the containment
    guarantee this shape is designed to uphold."""

    model_config = ConfigDict(frozen=True)

    system_instructions: str
    context_blocks: tuple[ContextBlock, ...] = ()
    user_instructions: str | None = None
    numeric_claims: tuple[NumericClaim, ...] = ()
    metadata: dict[str, str] = {}


class StructuredGenerationRequest(GenerationRequest):
    """A `GenerationRequest` additionally naming the structured output it targets.

    ``target_schema_name`` is descriptive only (used for logging/prompting hints); the
    actual pydantic schema class is passed separately to
    `LLMProvider.generate_structured` so the provider can validate its own output
    against it.
    """

    target_schema_name: str


class GenerationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    numeric_claims: tuple[NumericClaim, ...] = ()
    provider: str
    model: str
    finish_reason: str | None = None


class LLMProvider(Protocol):
    """The provider-agnostic interface. Any concrete provider (mock, Ollama Cloud, or a
    future one) implements this shape; callers depend only on the protocol."""

    async def health(self) -> ProviderHealth: ...

    async def generate(self, request: GenerationRequest) -> GenerationResult: ...

    async def generate_structured(
        self, request: StructuredGenerationRequest, schema: type[BaseModel]
    ) -> BaseModel: ...
