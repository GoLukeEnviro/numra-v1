"""The NUMRA LLM provider interface: a provider-agnostic protocol plus a deterministic
mock (used by CI/tests) and a real Ollama-compatible HTTP provider.

An LLM here may only explain/phrase already-validated results — see
`numra_interpretation.llm.validator` for the mechanism that enforces generated content
stays consistent with the `CanonicalProfile` it describes.
"""

from __future__ import annotations

from numra_interpretation.llm.mock_provider import MockLLMProvider
from numra_interpretation.llm.ollama_provider import OllamaCloudProvider, OllamaProviderError
from numra_interpretation.llm.types import (
    ContextBlock,
    GenerationRequest,
    GenerationResult,
    LLMProvider,
    NumericClaim,
    ProviderHealth,
    StructuredGenerationRequest,
)
from numra_interpretation.llm.validator import (
    build_metric_display_value_index,
    extract_placeholder_metric_ids,
    normalize_numeric_claims,
    validate_generation_result,
    validate_numeric_claims,
)

__all__ = [
    "ContextBlock",
    "GenerationRequest",
    "GenerationResult",
    "LLMProvider",
    "MockLLMProvider",
    "NumericClaim",
    "OllamaCloudProvider",
    "OllamaProviderError",
    "ProviderHealth",
    "StructuredGenerationRequest",
    "build_metric_display_value_index",
    "extract_placeholder_metric_ids",
    "normalize_numeric_claims",
    "validate_generation_result",
    "validate_numeric_claims",
]
