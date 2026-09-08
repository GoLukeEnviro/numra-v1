from __future__ import annotations

from enum import StrEnum


class ReportType(StrEnum):
    QUICK = "QUICK"
    FULL = "FULL"
    ULTIMATE = "ULTIMATE"
    CUSTOM = "CUSTOM"


class ReportJobStatus(StrEnum):
    QUEUED = "QUEUED"
    OUTLINE = "OUTLINE"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    ASSEMBLING = "ASSEMBLING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class NameIdentityKind(StrEnum):
    BIRTH = "birth"
    CURRENT = "current"
    PREFERRED = "preferred"


class ExportType(StrEnum):
    PDF = "pdf"
    JSON = "json"


class ExportStatus(StrEnum):
    PENDING = "pending"
    COMPLETE = "complete"
    FAILED = "failed"


class UserRole(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"


class AuditAction(StrEnum):
    USER_DISABLED = "USER_DISABLED"
    USER_ENABLED = "USER_ENABLED"
    USER_SESSIONS_REVOKED = "USER_SESSIONS_REVOKED"
    ADMIN_PROMOTED = "ADMIN_PROMOTED"


class PersonalTaskStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class InvitationMethod(StrEnum):
    LINK = "LINK"
    CODE = "CODE"
    EMAIL = "EMAIL"


class InvitationState(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class ConnectionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISSOLVED = "DISSOLVED"


class WorkspaceStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DISSOLVED = "DISSOLVED"


class WorkspaceMemberStatus(StrEnum):
    ACTIVE = "ACTIVE"
    REMOVED = "REMOVED"


class ConsentScope(StrEnum):
    CORE_NUMEROLOGY = "CORE_NUMEROLOGY"
    RELATIONSHIP_INSIGHTS = "RELATIONSHIP_INSIGHTS"
    CURRENT_TIMING = "CURRENT_TIMING"
    PRIVATE_JOURNAL = "PRIVATE_JOURNAL"
    PRIVATE_TASKS = "PRIVATE_TASKS"
    PRIVATE_COPILOT = "PRIVATE_COPILOT"
    OTHER_RELATIONSHIPS = "OTHER_RELATIONSHIPS"
    LIFE_TRACKING = "LIFE_TRACKING"


#: Auto-granted for both directions when a RelationshipWorkspace is created (see
#: services/connection_service.py). Every other ConsentScope value requires an
#: explicit grant via POST .../consent/grant.
DEFAULT_CONSENT_SCOPES: tuple[ConsentScope, ...] = (
    ConsentScope.CORE_NUMEROLOGY,
    ConsentScope.RELATIONSHIP_INSIGHTS,
    ConsentScope.CURRENT_TIMING,
)


class ConsentEventType(StrEnum):
    GRANTED = "GRANTED"
    REVOKED = "REVOKED"


class PersonAccountMode(StrEnum):
    """specs/v2/minor-profile-policy.md -- `person_account_mode` on `Person`. Only
    `SELF` profiles may ever become a `UserConnection` participant or
    `RelationshipWorkspace` member; `MANAGED_MINOR`/`MANAGED_OTHER` are private,
    single-owner profiles only."""

    SELF = "SELF"
    MANAGED_MINOR = "MANAGED_MINOR"
    MANAGED_OTHER = "MANAGED_OTHER"


class AnalysisJobStatus(StrEnum):
    """PR-V2-05 -- job lifecycle for `AnalysisJob` (relationship-analysis and
    shadow-dynamics generation). Deliberately fewer states than `ReportJobStatus`
    (no separate OUTLINE/ASSEMBLING phase -- see
    `numra_relationship_interpretation.pipeline`, which has no outline step)."""

    QUEUED = "QUEUED"
    GENERATING = "GENERATING"
    VALIDATING = "VALIDATING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class AnalysisType(StrEnum):
    """PR-V2-05 -- which pipeline an `AnalysisJob` runs."""

    RELATIONSHIP_INTERPRETATION = "RELATIONSHIP_INTERPRETATION"
    SHADOW_DYNAMICS = "SHADOW_DYNAMICS"


class RelationshipType(StrEnum):
    """specs/v2/relationship-type-spec.md -- selectable via PATCH
    /v1/workspaces/{workspace_id}. The canon never branches on this value, only the
    interpretation frame (out of scope for this PR, see PR-V2-05)."""

    PARTNER = "PARTNER"
    DATING = "DATING"
    FRIENDSHIP = "FRIENDSHIP"
    FAMILY = "FAMILY"
    SIBLINGS = "SIBLINGS"
    PARENT_CHILD = "PARENT_CHILD"
    WORK = "WORK"
    OTHER = "OTHER"


class TaskType(StrEnum):
    """PR-V2-07 -- specs/v2/task-system-spec.md. Deliberately its own value space,
    NOT shared with `PersonalTaskStatus` -- `PERSONAL_PRIVATE` tasks stay on the
    slim `PersonalTask` table (no `task_type` discriminator there at all, see
    models/tables.py::PersonalTask); every row on `WorkspaceTask` is one of the
    three relationship-facing types below."""

    FOR_PARTNER_PROPOSED = "FOR_PARTNER_PROPOSED"
    JOINT_SHARED = "JOINT_SHARED"
    AVENYTH_SUGGESTED = "AVENYTH_SUGGESTED"


class WorkspaceTaskStatus(StrEnum):
    """PR-V2-07 -- lifecycle of one `WorkspaceTask`
    (specs/v2/task-system-spec.md Lifecycle): PROPOSED -> ACCEPTED -> ACTIVE ->
    COMPLETED, or PROPOSED -> DECLINED, or any non-terminal state -> ARCHIVED.
    Server-authoritative -- no client ever writes this column directly except via
    the accept/decline/PATCH state-machine in services/workspace_task_service.py."""

    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    DECLINED = "DECLINED"
    ARCHIVED = "ARCHIVED"


class TaskAcceptanceEventType(StrEnum):
    """PR-V2-07 -- append-only audit trail for one `WorkspaceTask`
    (`TaskAcceptance`), same rationale/shape as `ConsentEventType` for
    `ConsentEvent`."""

    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    ACTIVATED = "ACTIVATED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class CheckinStatus(StrEnum):
    """PR-V2-06 -- lifecycle of one `RelationshipCheckin` cycle. `ANALYZED` is set
    synchronously, in the same transaction as the second member's submission, once
    `CheckinAnalysisService` has computed the shared derived result (see
    services/checkin_service.py::submit_checkin) -- there is no separate job/worker
    for this, unlike `ReportJobStatus`/`AnalysisJobStatus`."""

    AWAITING_SUBMISSIONS = "AWAITING_SUBMISSIONS"
    ANALYZED = "ANALYZED"


class RoadmapType(StrEnum):
    """PR-V2-08 -- specs/v2/roadmap-spec.md Types. Member names cannot start with a
    digit, hence the spelled-out names; the wire value is the spec's literal
    string."""

    FOURTEEN_DAY = "14_DAY"
    THIRTY_DAY = "30_DAY"
    QUARTER = "QUARTER"


class RoadmapStatus(StrEnum):
    """PR-V2-08 -- lifecycle of one `RelationshipRoadmap`
    (specs/v2/roadmap-spec.md Acceptance checks): PROPOSED -> ACCEPTED, or
    PROPOSED/ACCEPTED -> ARCHIVED. Server-authoritative, same discipline as
    `WorkspaceTaskStatus`."""

    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    ARCHIVED = "ARCHIVED"


class MilestoneType(StrEnum):
    """PR-V2-08 -- specs/v2/roadmap-spec.md Structure: a `RoadmapMilestone` row is
    either a concrete milestone or a review-point marker, discriminated by this
    column so both are filterable from the same table."""

    MILESTONE = "MILESTONE"
    REVIEW_POINT = "REVIEW_POINT"


class MilestoneStatus(StrEnum):
    """PR-V2-08 -- lifecycle of one `RoadmapMilestone`. `completed_at` is
    server-derived on the COMPLETED transition, only ever set via an explicit user
    PATCH (services/relationship_roadmap_service.py), never automatically."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class ThreadScope(StrEnum):
    """PR-V2-09 -- specs/v2/copilot-grounding-spec.md Thread model. Only
    `RELATIONSHIP_SHARED`/`RELATIONSHIP_PRIVATE` are ever created by a route in this
    PR -- `PERSONAL_PRIVATE`'s column shape (workspace_id NULL, owner_user_id set) is
    reserved on `ChatThread`/its CHECK constraint so PR-V2-09b can reuse this table
    without a migration, but no route/service in this PR creates that scope."""

    PERSONAL_PRIVATE = "PERSONAL_PRIVATE"
    RELATIONSHIP_PRIVATE = "RELATIONSHIP_PRIVATE"
    RELATIONSHIP_SHARED = "RELATIONSHIP_SHARED"


class ChatMessageRole(StrEnum):
    """PR-V2-09 -- who authored one `ChatMessage` row."""

    USER = "USER"
    ASSISTANT = "ASSISTANT"


class ChatMessageStatus(StrEnum):
    """PR-V2-09 -- lifecycle of one `ChatMessage` row. A USER row is always created
    COMPLETE (it needs no generation); an ASSISTANT row starts PENDING, moves through
    GENERATING while the synchronous Copilot pipeline runs, and ends COMPLETE or
    FAILED (services/copilot_service.py) -- there is no job/worker for this, unlike
    `AnalysisJobStatus` (interactive chat latency, specs/v2/copilot-grounding-spec.md)."""

    PENDING = "PENDING"
    GENERATING = "GENERATING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
