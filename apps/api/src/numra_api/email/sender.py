"""Where outbound transactional email (verification/reset links) actually goes.

`EmailSender` is a `Protocol` -- callers (`services/auth_recovery_service.py`) depend
only on its shape, never on a concrete implementation, so a real provider can be added
behind `Settings.email_backend` without touching any calling code (see
services/email_factory.py, the analogous `services/llm_factory.py`).

Three implementations exist: `LoggingEmailSender` only logs what would have been sent
(fine for local dev/CI/E2E, forbidden in production -- see
`Settings._forbid_logging_email_backend_in_production`); `DisabledEmailSender` is the
`numra_interpretation.llm.disabled_provider.DisabledLLMProvider` analogue -- every
`send()` call raises `EmailDeliveryUnavailable` immediately rather than one silently
pretending to have delivered; `SmtpEmailSender` (email/smtp_sender.py, kept in its own
module rather than growing this one -- it is the only implementation with real I/O and
its own dependency) is the real provider, `EMAIL_BACKEND=smtp`. Callers that go through
this on an unauthenticated, anti-enumeration-sensitive path (forgot-password) MUST
catch `EmailDeliveryUnavailable` themselves rather than let it propagate as an HTTP
error -- see services/auth_recovery_service.forgot_password.
"""

from __future__ import annotations

import logging
import re
from typing import Protocol

from numra_api.services.errors import EmailDeliveryUnavailable

__all__ = ["DisabledEmailSender", "EmailSender", "LoggingEmailSender"]

logger = logging.getLogger(__name__)


#: Any `?token=...` value in a rendered mail body. Recovery links (verify-email,
#: reset-password, connection redeem) all carry their credential this way.
_TOKEN_IN_URL = re.compile(r"([?&]token=)[^\s\"'&<>]+", re.IGNORECASE)


def _redact_recovery_tokens(text: str) -> str:
    """Replace a bearer token in a link with a placeholder, keeping the rest.

    `LoggingEmailSender` deliberately writes what it *would* have sent, so a
    developer or CI run can see the flow happened. The token is different: it is a
    working one-time credential for that account, and a log is the one artefact
    that reliably ends up pasted into an issue, a CI bundle or a screenshot. The
    link's shape and host stay visible -- only the secret is masked.
    """
    return _TOKEN_IN_URL.sub(r"\1<redacted>", text)


class EmailSender(Protocol):
    async def send(
        self, *, to: str, subject: str, body: str, html_body: str | None = None
    ) -> None: ...


class LoggingEmailSender:
    async def send(self, *, to: str, subject: str, body: str, html_body: str | None = None) -> None:
        logger.info(
            "email(to=%s, subject=%r, has_html=%s): %s",
            to,
            subject,
            html_body is not None,
            _redact_recovery_tokens(body),
        )


class DisabledEmailSender:
    async def send(self, *, to: str, subject: str, body: str, html_body: str | None = None) -> None:
        raise EmailDeliveryUnavailable("email was requested but EMAIL_BACKEND=disabled")
