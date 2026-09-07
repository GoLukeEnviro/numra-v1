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
