"""PWA-05: the dev/CI log backend must not print a recovery token in the clear.

`LoggingEmailSender` exists so a developer or CI run can see that a mail WOULD have
been sent. It wrote the whole body including the `?token=...` link, which turns any
log artefact -- a CI diagnostics bundle, a compose-log dump, a pasted terminal
buffer -- into a working one-time credential. The production validator already
forbids this backend in production, so the exposure is limited to dev/CI, but the
token is still a real credential for the account it belongs to.
"""

from __future__ import annotations

import logging

import pytest

from numra_api.email.sender import LoggingEmailSender

pytestmark = pytest.mark.unit

#: A realistic recovery link, with a recognisable token so the assertion cannot be
#: satisfied by accident.
TOKEN = "SENTINEL-TOKEN-VALUE-0123456789abcdef"
VERIFY_LINK = f"http://localhost:3000/verify-email?token={TOKEN}"
RESET_LINK = f"http://localhost:3000/reset-password?token={TOKEN}"


async def _send_and_capture(caplog, body: str) -> list[logging.LogRecord]:
    with caplog.at_level(logging.INFO, logger="numra_api.email.sender"):
        await LoggingEmailSender().send(
            to="dev@example.com", subject="Verify your AVENUM email address", body=body
        )
    return [r for r in caplog.records if r.name == "numra_api.email.sender"]


async def test_logging_sender_does_not_log_the_verification_token(caplog) -> None:
    records = await _send_and_capture(caplog, f"Confirm your email: {VERIFY_LINK}")

    assert records, "the logging backend must still record that a mail was attempted"
    combined = "\n".join(record.getMessage() for record in records)
    assert TOKEN not in combined, f"the recovery token leaked into the log: {combined!r}"


async def test_logging_sender_does_not_log_the_reset_token(caplog) -> None:
    records = await _send_and_capture(caplog, f"Reset your password: {RESET_LINK}")
    combined = "\n".join(record.getMessage() for record in records)
    assert TOKEN not in combined


async def test_logging_sender_still_says_what_it_would_have_sent(caplog) -> None:
    """Redaction must not gut the backend's purpose: recipient and subject stay."""
    records = await _send_and_capture(caplog, f"Confirm your email: {VERIFY_LINK}")

    combined = "\n".join(record.getMessage() for record in records)
    assert "dev@example.com" in combined
    assert "Verify your AVENUM email address" in combined
    # A developer still needs to know a link was present, and its host -- just not
    # the credential itself.
    assert "verify-email" in combined


async def test_redaction_keeps_prose_intact(caplog) -> None:
    """Ordinary body text must survive; only the credential is replaced."""
    records = await _send_and_capture(
        caplog, "If you did not request this, you can safely ignore this email."
    )
    combined = "\n".join(record.getMessage() for record in records)
    assert "you can safely ignore this email" in combined
