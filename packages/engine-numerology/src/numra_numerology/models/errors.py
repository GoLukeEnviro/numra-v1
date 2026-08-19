"""Explicit engine errors. NUMRA never silently falls back to a default/random value."""

from __future__ import annotations


class NumraEngineError(Exception):
    """Base class for all explicit NUMRA engine errors."""

    code: str = "NUMRA_ENGINE_ERROR"


class NormalizationUnsupportedScript(NumraEngineError):
    """Raised when a name contains characters outside A-Z after the full normalization
    pipeline (no automatic transliteration of non-Latin scripts is performed)."""

    code = "NORMALIZATION_UNSUPPORTED_SCRIPT"

    def __init__(self, original: str, remaining: str) -> None:
        self.original = original
        self.remaining = remaining
        super().__init__(f"{self.code}: unsupported characters {remaining!r} in {original!r}")


class InvalidDate(NumraEngineError):
    """Raised for a syntactically invalid date passed to a calculation."""

    code = "INVALID_DATE"


class NoRequiredName(NumraEngineError):
    """Raised when a required name field (birth first/last name) is missing or empty."""

    code = "NO_REQUIRED_NAME"


class FutureBirthDateNotAllowed(NumraEngineError):
    """Application-layer error: a person's birth date is after 'today' in the configured
    workspace timezone. The engine itself has no concept of 'today' and never raises this;
    it is raised by the application/API layer that wraps the engine."""

    code = "FUTURE_BIRTH_DATE_NOT_ALLOWED"
