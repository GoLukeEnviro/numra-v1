"""Builds the single `EmailSender` the app uses, from `Settings`.

This is the *only* place a concrete `EmailSender` class is chosen. `EMAIL_BACKEND` is
the sole source of truth for backend selection -- an unrecognized value is a bug, not
something to silently default away (see `build_llm_provider`, the template this
follows: no silent fallback there either).
"""

from __future__ import annotations

from numra_api.config import Settings
from numra_api.email.sender import DisabledEmailSender, EmailSender, LoggingEmailSender
from numra_api.email.smtp_sender import SmtpEmailSender

__all__ = ["build_email_sender"]


def build_email_sender(settings: Settings) -> EmailSender:
    """Construct the `EmailSender` selected by ``settings.email_backend``.

    ``Settings`` already forbids ``email_backend="logging"`` when
    ``environment="production"`` (see
    `Settings._forbid_logging_email_backend_in_production`) -- that check runs at
    settings-construction time, so by the time this factory runs the combination is
    already known to be safe. This function does not re-validate it; it trusts the
    `Settings` instance it is given.
    """
    if settings.email_backend == "logging":
        return LoggingEmailSender()
    if settings.email_backend == "disabled":
        return DisabledEmailSender()
    if settings.email_backend == "smtp":
        return SmtpEmailSender(settings)
    raise ValueError(f"unknown EMAIL_BACKEND: {settings.email_backend!r}")
