"""Where outbound transactional email (verification/reset links) actually goes.

`EmailSender` is a `Protocol` -- callers (`services/auth_recovery_service.py`) depend
only on its shape, never on a concrete implementation, so a future real provider
(SES/Postmark/...) can be added behind `Settings.email_backend` without touching any
calling code (see services/email_factory.py, the analogous `services/llm_factory.py`).

`LoggingEmailSender` and `DisabledEmailSender` are the only implementations in V1 (see
point 11 in the delegation brief: no pre-existing send mechanism in this repo) -- no
real provider exists yet. `LoggingEmailSender` only logs what would have been sent
(fine for local dev/CI/E2E, forbidden in production -- see
`Settings._forbid_logging_email_backend_in_production`). `DisabledEmailSender` is the
`numra_interpretation.llm.disabled_provider.DisabledLLMProvider` analogue: every
`send()` call raises `EmailDeliveryUnavailable` immediately rather than one silently
pretending to have delivered -- what a production deployment configures until a real
provider lands. Callers that go through this on an unauthenticated,
anti-enumeration-sensitive path (forgot-password) MUST catch it themselves rather than
let it propagate as an HTTP error -- see services/auth_recovery_service.forgot_password.
"""

from __future__ import annotations

import logging
from typing import Protocol

from numra_api.services.errors import EmailDeliveryUnavailable

__all__ = ["DisabledEmailSender", "EmailSender", "LoggingEmailSender"]

logger = logging.getLogger(__name__)


class EmailSender(Protocol):
    async def send(self, *, to: str, subject: str, body: str) -> None: ...


class LoggingEmailSender:
    async def send(self, *, to: str, subject: str, body: str) -> None:
        logger.info("email(to=%s, subject=%r): %s", to, subject, body)


class DisabledEmailSender:
    async def send(self, *, to: str, subject: str, body: str) -> None:
        raise EmailDeliveryUnavailable("email was requested but EMAIL_BACKEND=disabled")
