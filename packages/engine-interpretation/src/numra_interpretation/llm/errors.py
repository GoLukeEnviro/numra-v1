"""Normalized LLM provider exception taxonomy.

Every concrete provider (`OllamaCloudProvider`, any future one) maps its own
provider-specific failures onto these domain exceptions at its boundary, so callers
(the report job queue) never need to know which concrete provider raised something —
they only need `retryable` to decide whether to requeue the job or fail it.
"""

from __future__ import annotations

__all__ = [
    "LLMInvalidStructuredResponse",
    "LLMProviderError",
    "LLMProviderInternalError",
    "LLMProviderRateLimited",
    "LLMProviderTimeout",
    "LLMProviderUnavailable",
]


class LLMProviderError(Exception):
    """Base for any LLM-provider-level failure.

    ``retryable`` defaults to True: a network blip, timeout, rate limit, or malformed
    one-off response is generally worth trying again later. A provider/caller that
    knows a given failure is permanent should pass ``retryable=False`` explicitly.
    """

    retryable: bool = True

    def __init__(self, message: str, *, retryable: bool | None = None) -> None:
        super().__init__(message)
        if retryable is not None:
            self.retryable = retryable


class LLMProviderUnavailable(LLMProviderError):
    """The provider could not be reached at all (connection refused/DNS/etc.)."""


class LLMProviderTimeout(LLMProviderError):
    """The provider did not respond within the configured timeout."""


class LLMProviderRateLimited(LLMProviderError):
    """The provider responded with a rate-limit signal (e.g. HTTP 429)."""


class LLMInvalidStructuredResponse(LLMProviderError):
    """The provider responded, but its content was not valid JSON / did not match the
    requested schema. Still retryable by default — a fresh generation may succeed."""


class LLMProviderInternalError(LLMProviderError):
    """The provider responded with a server-side error (e.g. HTTP 5xx) or another
    unexpected failure that isn't one of the more specific categories above."""
