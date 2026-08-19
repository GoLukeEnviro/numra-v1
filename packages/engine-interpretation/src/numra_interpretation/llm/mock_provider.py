"""A fully deterministic, network-free `LLMProvider`. This is what CI uses — it must
never require network access, and given the same `GenerationRequest` it always returns
the same `GenerationResult` (no randomness, no wall-clock-dependent content beyond the
`ProviderHealth.checked_at` timestamp, which callers are not expected to assert on for
determinism)."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ValidationError

from numra_interpretation.llm.types import (
    GenerationRequest,
    GenerationResult,
    ProviderHealth,
    StructuredGenerationRequest,
)

__all__ = ["MockLLMProvider"]

_PROVIDER_NAME = "mock"
_MODEL_NAME = "mock-v1"


def _compose_text(request: GenerationRequest) -> str:
    """Deterministic, templated text built purely from the request's own fields — no
    generative model involved. Placeholders are resolved from ``numeric_claims`` when a
    matching metric_id is present, and left intact otherwise (a real provider would be
    expected to resolve or omit them; leaving them visible here lets tests exercise the
    placeholder-extraction path end-to-end)."""
    lines = [f"[system] {request.system_instructions}"]
    for block in request.context_blocks:
        lines.append(f"[{block.role}:{block.label}] {block.content}")
    if request.user_instructions is not None:
        # Kept as its own labeled, clearly delimited line — never merged into the
        # system_instructions text above.
        lines.append(f"[user_instructions] {request.user_instructions}")
    for claim in request.numeric_claims:
        lines.append(f"{{{{metric:{claim.metric_id}}}}} = {claim.display_value}")

    return "\n".join(lines)  # placeholders are left intact; see docstring above


class MockLLMProvider:
    """Deterministic mock conforming to the `LLMProvider` protocol. No network, no
    randomness, safe for CI."""

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            status="healthy",
            provider=_PROVIDER_NAME,
            checked_at=datetime.now(UTC),
            detail="mock provider is always healthy",
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        return GenerationResult(
            text=_compose_text(request),
            numeric_claims=request.numeric_claims,
            provider=_PROVIDER_NAME,
            model=_MODEL_NAME,
            finish_reason="stop",
        )

    async def generate_structured(
        self, request: StructuredGenerationRequest, schema: type[BaseModel]
    ) -> BaseModel:
        """Best-effort, deterministic construction of ``schema`` from the request.

        The mock recognizes two conventional field names on the target schema:

        - a ``text`` (or ``text_de``) field -> filled with the same composed text as
          `generate`.
        - a ``numeric_claims`` field -> filled with ``request.numeric_claims``
          (round-tripped verbatim, so callers can assert exact round-trip correctness).

        Any other required field with no default is left for pydantic to reject via its
        own `ValidationError` — the mock never invents a value for a field it does not
        understand, wrapped here only to add which schema/fields were the problem.
        """
        composed_text = _compose_text(request)
        candidate: dict[str, object] = {}
        for name, field in schema.model_fields.items():
            if name in ("text", "text_de"):
                candidate[name] = composed_text
            elif name == "numeric_claims":
                candidate[name] = list(request.numeric_claims)
            elif name == "metric_id" and request.numeric_claims:
                candidate[name] = request.numeric_claims[0].metric_id
            elif field.default is not None or not field.is_required():
                continue  # let pydantic apply the schema's own default
            # else: leave unset — pydantic will raise a clear ValidationError for a
            # required field the mock has no convention for.

        try:
            return schema.model_validate(candidate)
        except ValidationError as exc:
            raise ValueError(
                f"MockLLMProvider cannot construct {schema.__name__}: it only knows how "
                f"to fill conventional fields (text/text_de, numeric_claims, metric_id). "
                f"Underlying error: {exc}"
            ) from exc
