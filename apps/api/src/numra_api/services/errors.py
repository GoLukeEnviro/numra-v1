from __future__ import annotations


class ApplicationError(Exception):
    code: str = "APPLICATION_ERROR"
    status_code: int = 400


class FutureBirthDateNotAllowed(ApplicationError):
    code = "FUTURE_BIRTH_DATE_NOT_ALLOWED"
    status_code = 422


class NotFoundError(ApplicationError):
    code = "NOT_FOUND"
    status_code = 404


class InvalidCredentials(ApplicationError):
    code = "INVALID_CREDENTIALS"
    status_code = 401


class NotAuthenticated(ApplicationError):
    code = "NOT_AUTHENTICATED"
    status_code = 401


class SelfSignupDisabled(ApplicationError):
    code = "SELF_SIGNUP_DISABLED"
    status_code = 403


class EmailAlreadyRegistered(ApplicationError):
    code = "EMAIL_ALREADY_REGISTERED"
    status_code = 409


class Forbidden(ApplicationError):
    code = "FORBIDDEN"
    status_code = 403


class CsrfValidationFailed(ApplicationError):
    code = "CSRF_VALIDATION_FAILED"
    status_code = 403


class ReportNotReady(ApplicationError):
    code = "REPORT_NOT_READY"
    status_code = 409


class ExportRenderFailed(ApplicationError):
    code = "EXPORT_RENDER_FAILED"
    status_code = 502


class EmailDeliveryUnavailable(ApplicationError):
    """Raised by `email.sender.DisabledEmailSender.send` -- EMAIL_BACKEND=disabled
    means exactly that: no email is ever sent, and a caller must never be able to
    mistake this for success. An `ApplicationError` subclass (not a bare exception)
    so it is translated by app.py's central handler instead of surfacing as an
    unhandled 500; routes/auth.py::forgot_password additionally catches this
    specifically to preserve anti-enumeration (see its docstring)."""

    code = "EMAIL_DELIVERY_UNAVAILABLE"
    status_code = 503


class InvalidOrExpiredToken(ApplicationError):
    """Unified error for email-verification/password-reset tokens that are unknown,
    already consumed, or expired -- deliberately one shape for all three (see
    repositories/verification_tokens.py::claim_verification_token) so a caller can
    never distinguish "wrong token" from "token already used" from "token expired"."""

    code = "INVALID_OR_EXPIRED_TOKEN"
    status_code = 400


class RateLimitExceeded(ApplicationError):
    code = "RATE_LIMIT_EXCEEDED"
    status_code = 429

    def __init__(self, *, retry_after_seconds: int) -> None:
        super().__init__(f"rate limit exceeded, retry after {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds
