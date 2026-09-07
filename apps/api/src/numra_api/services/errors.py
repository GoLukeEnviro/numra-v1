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


class InvitationNotFound(ApplicationError):
    """IDOR-safe 404 for a missing/foreign `ConnectionInvitation` -- never a 403 (see
    PR-V2-03 blueprint: IDOR responses are always 404)."""

    code = "INVITATION_NOT_FOUND"
    status_code = 404


class InvitationExpiredOrInvalid(ApplicationError):
    """Unified error for invitations that are unknown, already redeemed/declined/
    revoked, or expired -- deliberately one shape for all of those (same rationale as
    `InvalidOrExpiredToken`), so a caller can never distinguish which."""

    code = "INVITATION_EXPIRED_OR_INVALID"
    status_code = 400


class CannotInviteSelf(ApplicationError):
    code = "CANNOT_INVITE_SELF"
    status_code = 422


class ConnectionAlreadyExists(ApplicationError):
    code = "CONNECTION_ALREADY_EXISTS"
    status_code = 409


class AdultAccountRequired(ApplicationError):
    """Never raised in PR-V2-03 -- every existing account is structurally adult per
    ADR-012. Defined now so PR-V2-04 (`person_account_mode`/minor profiles) can raise
    it without adding a new error shape later."""

    code = "ADULT_ACCOUNT_REQUIRED"
    status_code = 403


class ConsentNotGranted(ApplicationError):
    code = "CONSENT_NOT_GRANTED"
    status_code = 403


class WorkspaceDissolved(ApplicationError):
    code = "WORKSPACE_DISSOLVED"
    status_code = 409


class RelationshipTypeNotSet(ApplicationError):
    """Raised when a relationship-analysis/shadow-dynamics job is requested for a
    `RelationshipWorkspace` that has no `relationship_type` selected yet (PATCH
    /v1/workspaces/{workspace_id} must run first)."""

    code = "RELATIONSHIP_TYPE_NOT_SET"
    status_code = 409


class KnowledgeFrameNotAvailable(ApplicationError):
    """Raised when `numra_relationship_interpretation.knowledge_loader.load_relationship_frame`
    returns ``None`` for the workspace's `relationship_type` (e.g. `WORK`/`FAMILY` in
    this PR) -- a real, expected gap in the Knowledge Base content, not a bug."""

    code = "KNOWLEDGE_FRAME_NOT_AVAILABLE"
    status_code = 409


class SelfProfileRequired(ApplicationError):
    """Raised when one or both workspace members has no `SELF`-mode `Person` yet --
    relationship/shadow-dynamics analysis needs a real `CanonicalProfile` for both
    sides."""

    code = "SELF_PROFILE_REQUIRED"
    status_code = 409


class AmbiguousSelfProfile(ApplicationError):
    """Raised when a create/update would leave a user with more than one `SELF`-mode
    `Person` -- the DB-level arbiter is `uq_people_user_id_self_mode`
    (models/tables.py::Person), this is the translated `IntegrityError` (same
    rationale as `EmailAlreadyRegistered` in routes/auth.py::register)."""

    code = "AMBIGUOUS_SELF_PROFILE"
    status_code = 409
