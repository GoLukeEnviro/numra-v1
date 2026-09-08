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


class DimensionNotAllowedForRelationshipType(ApplicationError):
    """PR-V2-06 -- raised when a `sexual_connection`-class `CheckinDimension` is
    created/reactivated for a workspace whose `relationship_type` is one of
    `_RESTRICTED_RELATIONSHIP_TYPES` (see services/checkin_service.py). Server-side
    enforcement per specs/v2/checkin-spec.md, not just a UI hide."""

    code = "DIMENSION_NOT_ALLOWED_FOR_RELATIONSHIP_TYPE"
    status_code = 422


class CheckinAlreadySubmitted(ApplicationError):
    """PR-V2-06 -- a second submission attempt by the same user for the same
    `RelationshipCheckin` cycle. Append-only: there is no update path, so this is a
    conflict, not a validation error. The message deliberately carries only the
    `checkin_id`, never any submitted value (specs/v2/checkin-spec.md Privacy)."""

    code = "CHECKIN_ALREADY_SUBMITTED"
    status_code = 409

    def __init__(self, checkin_id: object) -> None:
        super().__init__(f"checkin {checkin_id} was already submitted by this user")


class SemanticKeyImmutable(ApplicationError):
    """PR-V2-06 -- raised when a custom-dimension create attempts to reuse a
    `semantic_key` that already exists (active or retired) for the workspace. A
    semantic redefinition of an existing key is never allowed -- retire it and
    introduce a new key instead (specs/v2/checkin-spec.md)."""

    code = "SEMANTIC_KEY_IMMUTABLE"
    status_code = 409


class InvalidRecipient(ApplicationError):
    """PR-V2-07 -- raised when a `POST .../tasks` body for `FOR_PARTNER_PROPOSED`
    supplies a `recipient_user_id` that is not the other ACTIVE member of the
    workspace. The recipient is always derived from workspace membership; the
    body field is only accepted for spoofing-detection (see
    services/workspace_task_service.py), never trusted as the source of truth."""

    code = "INVALID_RECIPIENT"
    status_code = 422


class AvenythSuggestedNotUserCreatable(ApplicationError):
    """PR-V2-07 -- `task_type=AVENYTH_SUGGESTED` may never be created via
    `POST .../tasks` -- only `services.workspace_task_service.
    create_avenyth_suggestion` (an internal function, no route) may create such a
    row (specs/v2/task-system-spec.md: server-authoritative provenance)."""

    code = "AVENYTH_SUGGESTED_NOT_USER_CREATABLE"
    status_code = 422


class TaskTransitionConflict(ApplicationError):
    """PR-V2-07 -- raised by accept/decline on a `WorkspaceTask` that is no longer
    in `PROPOSED` state (e.g. a second accept/decline attempt) -- a conflict, not
    a validation error, same rationale as `CheckinAlreadySubmitted`."""

    code = "TASK_TRANSITION_CONFLICT"
    status_code = 409


class TaskNotDeletable(ApplicationError):
    """PR-V2-07 -- raised by DELETE .../tasks/{task_id} unless the task is
    PROPOSED/DECLINED/ARCHIVED (an ACTIVE/ACCEPTED/COMPLETED task must be
    archived first, never deleted directly)."""

    code = "TASK_NOT_DELETABLE"
    status_code = 422


class RoadmapTransitionConflict(ApplicationError):
    """PR-V2-08 -- raised by PATCH .../roadmaps/{roadmap_id} status=ACCEPTED on a
    `RelationshipRoadmap` that is no longer PROPOSED (e.g. a second accept
    attempt) -- a conflict, not a validation error, same rationale as
    `TaskTransitionConflict`."""

    code = "ROADMAP_TRANSITION_CONFLICT"
    status_code = 409


class RoadmapNotDeletable(ApplicationError):
    """PR-V2-08 -- raised by DELETE .../roadmaps/{roadmap_id} unless the roadmap is
    PROPOSED/ARCHIVED (an ACCEPTED roadmap must be archived first, never deleted
    directly)."""

    code = "ROADMAP_NOT_DELETABLE"
    status_code = 422


class RoadmapArchived(ApplicationError):
    """PR-V2-08 -- raised by PATCH .../roadmaps/{roadmap_id} (title/roadmap_type)
    once the roadmap is ARCHIVED -- an archived roadmap is read-only."""

    code = "ROADMAP_ARCHIVED"
    status_code = 422


class InvalidRoadmapStatusTransition(ApplicationError):
    """PR-V2-08 -- raised when PATCH .../roadmaps/{roadmap_id} is given a `status`
    value other than ACCEPTED/ARCHIVED, or a transition that isn't legal from the
    roadmap's current state (e.g. ARCHIVED -> ACCEPTED)."""

    code = "INVALID_ROADMAP_STATUS_TRANSITION"
    status_code = 422


class MilestoneNotInWorkspace(ApplicationError):
    """PR-V2-08 -- raised when a `workspace_tasks.roadmap_milestone_id` link is
    set to a `RoadmapMilestone` that does not belong to the task's own
    `workspace_id` (specs/v2 build order: Task<->Milestone link, cross-workspace
    must be rejected, never silently cross-linked)."""

    code = "MILESTONE_NOT_IN_WORKSPACE"
    status_code = 422


class MetricKeyImmutable(ApplicationError):
    """PR-V2-11 -- eine `CustomMetricDefinition` mit diesem `metric_key` existiert
    fuer die Person bereits (aktiv oder stillgelegt). Gleiche Regel und gleiche
    Begruendung wie `SemanticKeyImmutable`: ein Key darf nie semantisch umgedeutet
    werden, weil bereits erfasste `LifeTrackingMetricValue`-Zeilen ihn tragen."""

    code = "METRIC_KEY_IMMUTABLE"
    status_code = 409


class MetricValueOutOfScale(ApplicationError):
    """PR-V2-11 -- ein Custom-Metrik-Wert liegt ausserhalb der `scale_min`/
    `scale_max` seiner eigenen `CustomMetricDefinition`. Die fuenf festen Metriken
    brauchen das nicht: deren 1..10-Grenze steht im Pydantic-Schema UND als
    CHECK-Constraint auf `life_tracking_entries`; eine Custom-Skala ist dagegen pro
    Definition frei und daher nur zur Laufzeit pruefbar."""

    code = "METRIC_VALUE_OUT_OF_SCALE"
    status_code = 422


class EvidencePolicyNotFound(ApplicationError):
    """PR-V2-11 -- keine aktive `EvidencePolicy` in der Datenbank. Ein
    Deployment-Fehler, kein Nutzerfehler: die Migration
    `d4e5f6a7b8c9_evidence_layer` seedet Version 1, und ohne Policy darf ueberhaupt
    keine Korrelationsaussage entstehen (specs/v2/evidence-policy.md: nie eine ad
    hoc gewaehlte Schwelle). Deshalb 503 statt eines stillen Defaults."""

    code = "EVIDENCE_POLICY_NOT_FOUND"
    status_code = 503


class EvidenceStatementLintFailed(ApplicationError):
    """PR-V2-11 -- `numra_interpretation.report.evidence_linter.
    lint_structured_statement` hat ein bereits berechnetes Ergebnis abgelehnt. Das
    ist strukturell unerreichbar, solange das feste Template in
    `services/evidence_analysis_service.py` die Quelle ist -- die Pruefung ist die
    Sicherung dagegen, dass eine spaetere Aenderung dort still einen Pflicht-
    Qualifier verliert. Lieber 500 als eine Aussage ohne Stichprobengroesse,
    Beobachtungszeitraum und Konfidenzkategorie ausliefern."""

    code = "EVIDENCE_STATEMENT_LINT_FAILED"
    status_code = 500


class ThreadArchiveForbidden(ApplicationError):
    """PR-V2-09 -- raised by `services/copilot_service.py::archive_thread_route`
    when the caller may not archive a `ChatThread`: RELATIONSHIP_PRIVATE is
    owner-only (an ACTIVE partner still may not archive the requester's private
    thread, even though membership alone passes the IDOR gate)."""

    code = "THREAD_ARCHIVE_FORBIDDEN"
    status_code = 403
