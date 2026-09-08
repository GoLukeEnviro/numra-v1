from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import (
    true as sa_true,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from numra_api.db import Base
from numra_api.models.enums import (
    AnalysisJobStatus,
    AnalysisType,
    CheckinStatus,
    ConnectionStatus,
    ExportStatus,
    ExportType,
    InvitationMethod,
    InvitationState,
    NameIdentityKind,
    PersonAccountMode,
    PersonalTaskStatus,
    ReportJobStatus,
    ReportType,
    TaskAcceptanceEventType,
    TaskType,
    UserRole,
    WorkspaceMemberStatus,
    WorkspaceStatus,
    WorkspaceTaskStatus,
)


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[UserRole] = mapped_column(String(20), default=UserRole.USER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    #: NULL means "not yet verified". Set once, by the atomic claim in
    #: routes/auth.py::verify_email -- never cleared afterwards. Existing V1.6 accounts
    #: are grandfathered to their `created_at` by the migration that adds this column
    #: (see alembic/versions -- no bulk unverified backlog).
    email_verified_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sessions: Mapped[list[Session]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    people: Mapped[list[Person]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="sessions")


class Person(Base):
    __tablename__ = "people"
    __table_args__ = (
        #: Partial unique index -- at most one SELF-mode Person per user, DB-enforced
        #: (not just checked in the service layer), analogous to
        #: `UserConnection.uq_user_connections_pair` (see PR-V2-03). `text(...)` on the
        #: not-yet-bound mapped_column attributes, same Context7-verified pattern.
        Index(
            "uq_people_user_id_self_mode",
            "user_id",
            unique=True,
            postgresql_where=text("person_account_mode = 'SELF'"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    #: specs/v2/minor-profile-policy.md -- SELF | MANAGED_MINOR | MANAGED_OTHER. Only
    #: `SELF` profiles may become a `UserConnection`/`RelationshipWorkspace` member.
    #: `server_default="SELF"` grandfathers every pre-PR-V2-04 row (see the migration's
    #: backfill, which then re-derives the true value per user_id).
    person_account_mode: Mapped[PersonAccountMode] = mapped_column(
        String(20), nullable=False, server_default="SELF"
    )

    birth_first_names: Mapped[str] = mapped_column(String(200))
    birth_middle_names: Mapped[str | None] = mapped_column(String(200), nullable=True)
    birth_last_name: Mapped[str] = mapped_column(String(200))
    birth_date: Mapped[dt.date] = mapped_column(Date)
    birth_time: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    birth_place: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    current_first_names: Mapped[str | None] = mapped_column(String(200), nullable=True)
    current_middle_names: Mapped[str | None] = mapped_column(String(200), nullable=True)
    current_last_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    preferred_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="people")
    name_identities: Mapped[list[NameIdentity]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )
    calculations: Mapped[list[Calculation]] = relationship(
        back_populates="person", cascade="all, delete-orphan"
    )


class NameIdentity(Base):
    __tablename__ = "name_identities"

    id: Mapped[uuid.UUID] = _uuid_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[NameIdentityKind] = mapped_column(String(20))
    first_names: Mapped[str] = mapped_column(String(200))
    middle_names: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_name: Mapped[str] = mapped_column(String(200))
    valid_from: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    person: Mapped[Person] = relationship(back_populates="name_identities")


class Calculation(Base):
    """Immutable snapshot of one engine run. Never mutated after creation — a
    recalculation creates a new row (calculation revision)."""

    __tablename__ = "calculations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), index=True
    )
    calculation_version: Mapped[str] = mapped_column(String(20))
    schema_version: Mapped[str] = mapped_column(String(20))
    as_of_date: Mapped[dt.date] = mapped_column(Date)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    canonical_profile_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    deterministic_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    person: Mapped[Person] = relationship(back_populates="calculations")


class RelationshipComparison(Base):
    __tablename__ = "relationships"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    calculation_a_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calculations.id", ondelete="CASCADE")
    )
    calculation_b_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calculations.id", ondelete="CASCADE")
    )
    comparison_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    #: V1.5 Epic F -- structured, knowledge-sourced qualitative notes (list of
    #: per-metric insight dicts). Snapshotted at creation time like `comparison_json`,
    #: never a compatibility score.
    insights_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default="[]", nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    calculation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calculations.id", ondelete="CASCADE")
    )
    report_type: Mapped[ReportType] = mapped_column(String(20))

    calculation_version: Mapped[str] = mapped_column(String(20))
    knowledge_version: Mapped[str] = mapped_column(String(20))
    prompt_version: Mapped[str] = mapped_column(String(40))
    model_provider: Mapped[str | None] = mapped_column(String(60), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    profile_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    report_schema_version: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    generated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sections: Mapped[list[ReportSection]] = relationship(
        back_populates="report", cascade="all, delete-orphan", order_by="ReportSection.order_index"
    )
    jobs: Mapped[list[ReportJob]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class ReportSection(Base):
    __tablename__ = "report_sections"

    id: Mapped[uuid.UUID] = _uuid_pk()
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    section_id: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(200))
    order_index: Mapped[int] = mapped_column(Integer)
    content_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    report: Mapped[Report] = relationship(back_populates="sections")


class ReportJob(Base):
    __tablename__ = "report_jobs"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "idempotency_key", name="uq_report_jobs_user_id_idempotency_key"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    status: Mapped[ReportJobStatus] = mapped_column(String(20), default=ReportJobStatus.QUEUED)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: When a retryable failure occurs, the job is requeued (status reset to QUEUED)
    #: but must not be reclaimed again until this timestamp (exponential backoff).
    #: NULL means "immediately reclaimable" (fresh job / no backoff pending).
    next_attempt_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    report: Mapped[Report] = relationship(back_populates="jobs")
    llm_generations: Mapped[list[LLMGeneration]] = relationship(
        back_populates="report_job", cascade="all, delete-orphan"
    )


class LLMGeneration(Base):
    """PII-safe LLM call log — never stores the full prompt or report content by
    default, only metadata (provider/model/status/latency/prompt_hash/section_id)."""

    __tablename__ = "llm_generations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    report_job_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("report_jobs.id", ondelete="CASCADE"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(60))
    model: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20))
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    prompt_hash: Mapped[str] = mapped_column(String(64))
    section_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    report_job: Mapped[ReportJob | None] = relationship(back_populates="llm_generations")


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reports.id", ondelete="CASCADE"), nullable=True
    )
    export_type: Mapped[ExportType] = mapped_column(String(20))
    status: Mapped[ExportStatus] = mapped_column(String(20), default=ExportStatus.PENDING)
    #: Opaque storage reference returned by ExportStorage.save() — never a
    #: client-controllable path (see numra_api/storage/exports.py).
    file_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AdminAuditEvent(Base):
    """Minimal privileged-action audit log. Decoupled from User's cascade behavior
    on purpose (ondelete=SET NULL, no back_populates) so audit history survives
    even if a referenced user account is ever deleted. Never stores passwords,
    session tokens, or password hashes -- `safe_metadata` is for non-secret
    context only (e.g. the acting admin's email, not their credentials)."""

    __tablename__ = "admin_audit_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50))
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EmailVerificationToken(Base):
    """Single-use, hashed bearer token proving control of the account's email
    address. Same shape as `Session`/`PasswordResetToken` (only the hash is stored,
    `consumed_at` marks single use) -- see auth/tokens.py for the shared
    generate/hash primitives."""

    __tablename__ = "email_verification_tokens"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PasswordResetToken(Base):
    """Single-use, hashed bearer token authorizing one password reset. Deliberately
    its own table rather than reusing `EmailVerificationToken` -- the two flows must
    never be able to consume each other's tokens."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EntitlementSet(Base):
    """A named bundle of feature flags/limits (e.g. "beta_default"). Not itself
    user-scoped -- `EntitlementAssignment` is the join between a `User` and one of
    these. `max_connections`/`max_workspaces` of NULL means unlimited."""

    __tablename__ = "entitlement_sets"

    id: Mapped[uuid.UUID] = _uuid_pk()
    key: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    personal_workspace: Mapped[bool] = mapped_column(Boolean, server_default=sa_true())
    connections: Mapped[bool] = mapped_column(Boolean, server_default=sa_true())
    relationship_workspaces: Mapped[bool] = mapped_column(Boolean, server_default=sa_true())
    relationship_checkins: Mapped[bool] = mapped_column(Boolean, server_default=sa_true())
    relationship_copilot: Mapped[bool] = mapped_column(Boolean, server_default=sa_true())
    advanced_relationship_analysis: Mapped[bool] = mapped_column(Boolean, server_default=sa_true())
    life_tracking: Mapped[bool] = mapped_column(Boolean, server_default=sa_true())
    premium_reports: Mapped[bool] = mapped_column(Boolean, server_default=sa_true())
    max_connections: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_workspaces: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EntitlementAssignment(Base):
    """Which `EntitlementSet` one `User` currently has. `user_id` is unique -- a user
    has at most one active assignment; a user with none falls back to the
    "beta_default" `EntitlementSet` (see routes/entitlements.py). `entitlement_set_id`
    uses `ondelete="RESTRICT"` (unlike the CASCADE everywhere else here) -- an
    `EntitlementSet` still referenced by an assignment must not be deletable out from
    under it."""

    __tablename__ = "entitlement_assignments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    entitlement_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entitlement_sets.id", ondelete="RESTRICT")
    )
    assigned_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PrivateReflection(Base):
    """PERSONAL_PRIVATE Workspace surface (specs/v2/personal-workspace-spec.md) --
    never shared unless the user performs an explicit SHARE action into a
    relationship context (out of scope for this PR). `user_id` is the IDOR security
    boundary (repository queries always filter on it), `person_id` is the fachliche
    Zuordnung -- both columns are stored, see repositories/private_reflections.py."""

    __tablename__ = "private_reflections"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), index=True
    )
    entry_date: Mapped[dt.date] = mapped_column(Date)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PrivateNote(Base):
    """PERSONAL_PRIVATE Workspace surface, same shape/ownership rules as
    `PrivateReflection` -- see that class's docstring."""

    __tablename__ = "private_notes"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PersonalTask(Base):
    """PERSONAL_PRIVATE Workspace surface. Deliberately its own slim table -- no
    `task_type` discriminator (every row is PERSONAL_PRIVATE by construction) and no
    `workspace_id` (the V2 `WorkspaceTask`/relationship-task-system entities do not
    exist yet -- see specs/v2/data-model.md). `completed_at` is set automatically by
    the route when `status` transitions to COMPLETED (see
    routes/personal_tasks.py), never accepted directly from the client."""

    __tablename__ = "personal_tasks"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    status: Mapped[PersonalTaskStatus] = mapped_column(
        String(20), default=PersonalTaskStatus.ACTIVE
    )
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ConnectionInvitation(Base):
    """Outbound invite to form a `UserConnection`. Always references the inviter's
    `user_id` -- there is no `person_id` on this table (a Connection is a
    User<->User relationship, see PR-V2-03 blueprint). `invitee_email` is only
    populated for `method=EMAIL` invites; LINK/CODE invites carry no PII and are
    redeemed purely off `token_hash`. Anti-enumeration for EMAIL invites lives in
    services/connection_service.py, not here."""

    __tablename__ = "connection_invitations"

    id: Mapped[uuid.UUID] = _uuid_pk()
    inviter_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    method: Mapped[InvitationMethod] = mapped_column(String(20))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    invitee_email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    state: Mapped[InvitationState] = mapped_column(String(20), default=InvitationState.PENDING)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    redeemed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    redeemed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserConnection(Base):
    """A confirmed User<->User connection, born from one accepted
    `ConnectionInvitation`. `user_a_id`/`user_b_id` are unordered -- the expression
    unique index below (LEAST/GREATEST) prevents a duplicate pairing regardless of
    which side is stored as A vs. B, DB-enforced against races (not just checked in
    the service layer). 1:1 with a `RelationshipWorkspace` once created."""

    __tablename__ = "user_connections"
    __table_args__ = (
        CheckConstraint("user_a_id <> user_b_id", name="ck_user_connections_distinct_users"),
        #: Expression unique index -- order-independent pairing guard, enforced at the
        #: DB level regardless of which side is stored as A vs. B (race-safe, unlike a
        #: service-layer check). `sa.text(...)` rather than `func.least(...)` on the
        #: not-yet-bound mapped_column attributes -- see PR-V2-03 Context7 lookup.
        Index(
            "uq_user_connections_pair",
            text("LEAST(user_a_id, user_b_id)"),
            text("GREATEST(user_a_id, user_b_id)"),
            unique=True,
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_a_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    user_b_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[ConnectionStatus] = mapped_column(String(20), default=ConnectionStatus.ACTIVE)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    dissolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RelationshipWorkspace(Base):
    """Placeholder shared workspace for one `UserConnection` -- no content columns yet
    (see PR-V2-03 blueprint; content surfaces land in later PRs). 1:1 with its
    `UserConnection` via the unique FK below."""

    __tablename__ = "relationship_workspaces"

    id: Mapped[uuid.UUID] = _uuid_pk()
    connection_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_connections.id", ondelete="CASCADE"), unique=True, index=True
    )
    status: Mapped[WorkspaceStatus] = mapped_column(String(20), default=WorkspaceStatus.ACTIVE)
    #: specs/v2/relationship-type-spec.md -- nullable (unset until a member chooses one
    #: via PATCH /v1/workspaces/{workspace_id}). The canon never branches on this value;
    #: only the (later, PR-V2-05) interpretation frame does.
    relationship_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    dissolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkspaceMember(Base):
    """One `User`'s membership row in a `RelationshipWorkspace` -- always exactly two
    ACTIVE rows per workspace (created atomically alongside it, see
    services/connection_service.py)."""

    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "user_id", name="uq_workspace_members_workspace_id_user_id"
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationship_workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[WorkspaceMemberStatus] = mapped_column(
        String(20), default=WorkspaceMemberStatus.ACTIVE
    )
    joined_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ConsentGrant(Base):
    """One directional consent: `grantor_user_id` allows `grantee_user_id` to see
    `scope` within `workspace_id`. `version` is always 1 in this PR (no re-grant flow
    yet) -- see services/consent_service.py::assert_consent for the enforcement read
    path (always fresh from DB, no caching)."""

    __tablename__ = "consent_grants"
    __table_args__ = (
        CheckConstraint(
            "grantor_user_id <> grantee_user_id", name="ck_consent_grants_distinct_users"
        ),
        UniqueConstraint(
            "workspace_id",
            "grantor_user_id",
            "grantee_user_id",
            "scope",
            "version",
            name="uq_consent_grants_workspace_grantor_grantee_scope_version",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationship_workspaces.id", ondelete="CASCADE"), index=True
    )
    grantor_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    grantee_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    scope: Mapped[str] = mapped_column(String(40))
    version: Mapped[int] = mapped_column(Integer, default=1)
    granted_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConsentEvent(Base):
    """Append-only audit trail for one `ConsentGrant` -- one row per GRANTED/REVOKED
    transition. `actor_user_id` uses `ondelete=SET NULL` (audit-reference pattern,
    see `AdminAuditEvent`) so history survives a deleted account."""

    __tablename__ = "consent_events"

    id: Mapped[uuid.UUID] = _uuid_pk()
    grant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("consent_grants.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(20))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    occurred_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AnalysisJob(Base):
    """PR-V2-05 -- job lifecycle for one relationship-analysis or shadow-dynamics
    generation, same shape/rationale as `ReportJob` (SELECT...FOR UPDATE SKIP LOCKED
    claiming, lease/backoff retry columns, idempotency). ``requested_by_user_id`` is
    whichever workspace member triggered the job -- both members may later read the
    result (see `repositories/analysis.py::get_analysis_job_for_user`), not just the
    requester."""

    __tablename__ = "analysis_jobs"
    __table_args__ = (
        Index(
            "uq_analysis_jobs_user_id_idempotency_key",
            "requested_by_user_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationship_workspaces.id", ondelete="CASCADE"), index=True
    )
    requested_by_user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    analysis_type: Mapped[AnalysisType] = mapped_column(String(40))
    status: Mapped[AnalysisJobStatus] = mapped_column(String(20), default=AnalysisJobStatus.QUEUED)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_until: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RelationshipAnalysis(Base):
    """PR-V2-05 -- one completed (or in-progress) relationship-analysis result,
    1:1 with the `AnalysisJob` that produced it. `relationship_type` is a snapshot
    (the workspace's type may change later) -- same rationale as
    `Report.report_type` snapshotting `report_type` independent of later changes."""

    __tablename__ = "relationship_analyses"

    id: Mapped[uuid.UUID] = _uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationship_workspaces.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"), unique=True
    )
    relationship_type: Mapped[str] = mapped_column(String(20))
    calculation_a_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calculations.id", ondelete="CASCADE")
    )
    calculation_b_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calculations.id", ondelete="CASCADE")
    )
    calculation_version: Mapped[str] = mapped_column(String(20))
    knowledge_version: Mapped[str] = mapped_column(String(20))
    prompt_version: Mapped[str] = mapped_column(String(40))
    model_provider: Mapped[str | None] = mapped_column(String(60), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    generated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ShadowDynamicsAnalysis(Base):
    """PR-V2-05 -- one completed (or in-progress) shadow-dynamics result. Same shape
    as `RelationshipAnalysis` (its own table/job_id FK, see blueprint: "identisches
    Grundmuster") -- kept as a separate table rather than a discriminator column so
    each result type can evolve its own columns independently."""

    __tablename__ = "shadow_dynamics_analyses"

    id: Mapped[uuid.UUID] = _uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationship_workspaces.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_jobs.id", ondelete="CASCADE"), unique=True
    )
    relationship_type: Mapped[str] = mapped_column(String(20))
    calculation_a_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calculations.id", ondelete="CASCADE")
    )
    calculation_b_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("calculations.id", ondelete="CASCADE")
    )
    calculation_version: Mapped[str] = mapped_column(String(20))
    knowledge_version: Mapped[str] = mapped_column(String(20))
    prompt_version: Mapped[str] = mapped_column(String(40))
    model_provider: Mapped[str | None] = mapped_column(String(60), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    result_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    generated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CheckinTemplate(Base):
    """specs/v2/checkin-spec.md -- one versioned dimension set for a
    `RelationshipWorkspace`. Lazily created on first check-in access (see
    services/checkin_service.py::get_or_create_active_template), never in
    services/connection_service.py::accept_invitation. `version` is a plain
    monotonically increasing integer per workspace (no re-versioning flow yet in this
    PR -- exactly one `active=True` row per workspace at a time)."""

    __tablename__ = "checkin_templates"
    __table_args__ = (
        UniqueConstraint("workspace_id", "version", name="uq_checkin_templates_workspace_version"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationship_workspaces.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    active: Mapped[bool] = mapped_column(Boolean, server_default=sa_true())
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CheckinDimension(Base):
    """specs/v2/checkin-spec.md -- one configurable dimension (`closeness`,
    `communication`, ... or a custom key) within a workspace's template.
    `semantic_key` is provably immutable once referenced by any `CheckinResponse` --
    enforced by `uq_checkin_dimensions_workspace_semantic_key` (one semantic_key ever
    exists per workspace, never duplicated even across template versions) plus the
    app-level check in services/checkin_service.py (a reused key raises
    `SemanticKeyImmutable`). `retired_at` is a deliberate soft-delete exception (see
    coding-style "kein Dead Code" -- this is not dead code, historical
    `CheckinResponse`/`CheckinAnalysis` rows keep referencing the row via
    `semantic_key`/`dimension_id`, so it must never be hard-deleted). A label/
    description edit mutates this row in place; a semantic redefinition is not
    allowed -- that requires retiring this row and creating a new `semantic_key`."""

    __tablename__ = "checkin_dimensions"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "semantic_key", name="uq_checkin_dimensions_workspace_semantic_key"
        ),
        CheckConstraint("scale_min < scale_max", name="ck_checkin_dimensions_scale_min_lt_max"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationship_workspaces.id", ondelete="CASCADE"), index=True
    )
    template_version: Mapped[int] = mapped_column(Integer)
    semantic_key: Mapped[str] = mapped_column(String(60))
    label: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scale_min: Mapped[int] = mapped_column(Integer, default=1)
    scale_max: Mapped[int] = mapped_column(Integer, default=10)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active: Mapped[bool] = mapped_column(Boolean, server_default=sa_true())
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    retired_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RelationshipCheckin(Base):
    """specs/v2/checkin-spec.md -- one check-in cycle for a workspace.
    `checkin_template_version` is a snapshot integer (like `Report.report_type`), NOT
    a FK to `CheckinTemplate.id` -- the template may gain new versions later without
    rewriting history. Synchronous status transition, no job/worker: `ANALYZED` is
    set in the same transaction as the second member's submission (see
    services/checkin_service.py::submit_checkin)."""

    __tablename__ = "relationship_checkins"

    __table_args__ = (
        #: Race-safety net for two members submitting their first response for a new
        #: round at (near-)the same time: without this, both concurrent transactions
        #: read `get_awaiting_checkin` -> None under READ COMMITTED (neither commit is
        #: visible yet) and each creates its own round, so the two submissions never
        #: land on the same `RelationshipCheckin` and the analysis never triggers. A
        #: partial unique index makes the loser's INSERT fail with an IntegrityError
        #: instead, which `submit_checkin` catches and retries against the winner's
        #: round (see services/checkin_service.py).
        Index(
            "uq_relationship_checkins_one_awaiting_per_workspace",
            "workspace_id",
            unique=True,
            postgresql_where=text("status = 'AWAITING_SUBMISSIONS'"),
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationship_workspaces.id", ondelete="CASCADE"), index=True
    )
    checkin_template_version: Mapped[int] = mapped_column(Integer)
    cycle_started_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[CheckinStatus] = mapped_column(
        String(20), default=CheckinStatus.AWAITING_SUBMISSIONS
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CheckinResponse(Base):
    """specs/v2/checkin-spec.md Privacy (Section 19) -- raw answers are
    `SUBMITTER_ONLY`. `user_id` is the IDOR/privacy boundary: every repository read of
    this table must filter on it (see repositories/checkins.py::
    get_responses_for_checkin_and_user) -- there must be no repository function that
    returns raw values without a `user_id` filter reachable from a route. Append-only
    (no update path): `uq_checkin_responses_checkin_user_dimension` guarantees at
    most one value per (checkin, user, dimension) -- a second submission attempt for
    the same round raises `CheckinAlreadySubmitted` rather than overwriting.
    `semantic_key` is denormalized from `CheckinDimension` so trend aggregation can
    group strictly by `(semantic_key, checkin_template_version)` without a join, per
    the spec's segmentation rule."""

    __tablename__ = "checkin_responses"
    __table_args__ = (
        UniqueConstraint(
            "checkin_id",
            "user_id",
            "dimension_id",
            name="uq_checkin_responses_checkin_user_dimension",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    checkin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationship_checkins.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    dimension_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("checkin_dimensions.id", ondelete="CASCADE")
    )
    semantic_key: Mapped[str] = mapped_column(String(60))
    value: Mapped[int] = mapped_column(Integer)
    submitted_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CheckinAnalysis(Base):
    """specs/v2/checkin-spec.md Deterministic analysis (Section 20) -- one
    LLM-free, deterministically computed shared result per `RelationshipCheckin`
    (1:1 via the unique FK below), produced by
    services/checkin_analysis_service.py. `result_json` shape:
    ``{semantic_key: {absolute_gap, direction, rolling_trend, sample_size,
    historical_delta, sufficient_evidence}}`` -- never raw per-user values, only the
    already-aggregated gap/trend numbers both members may see."""

    __tablename__ = "checkin_analyses"

    id: Mapped[uuid.UUID] = _uuid_pk()
    checkin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationship_checkins.id", ondelete="CASCADE"), unique=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationship_workspaces.id", ondelete="CASCADE"), index=True
    )
    checkin_template_version: Mapped[int] = mapped_column(Integer)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSONB)
    computed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class WorkspaceTask(Base):
    """PR-V2-07 -- specs/v2/task-system-spec.md. Deliberately a separate table from
    `PersonalTask` (see that class's docstring) -- `task_type` discriminates the
    three relationship-facing kinds (`TaskType`). `source_analysis_id` is
    intentionally NOT a FK (polymorph provenance pointer, no single target table
    yet) -- only ever set for `AVENYTH_SUGGESTED` rows, enforced by
    `ck_workspace_tasks_provenance_only_avenyth_suggested`. `completed_at` is
    server-derived on the COMPLETED transition, same discipline as
    `PersonalTask.completed_at` (see services/workspace_task_service.py, never
    accepted directly from a client)."""

    __tablename__ = "workspace_tasks"
    __table_args__ = (
        CheckConstraint(
            "task_type = 'AVENYTH_SUGGESTED' OR "
            "(source_analysis_id IS NULL AND prompt_version IS NULL "
            "AND knowledge_version IS NULL)",
            name="ck_workspace_tasks_provenance_only_avenyth_suggested",
        ),
        #: One CHECK covering all three `task_type` cases (analogous to
        #: `ck_user_connections_distinct_users`'s single-expression style):
        #: FOR_PARTNER_PROPOSED needs both proposer and recipient set,
        #: JOINT_SHARED needs a proposer but no recipient, AVENYTH_SUGGESTED needs
        #: no proposer (recipient irrelevant -- whichever member accepts it).
        CheckConstraint(
            "(task_type = 'FOR_PARTNER_PROPOSED' "
            "AND proposer_user_id IS NOT NULL AND recipient_user_id IS NOT NULL) "
            "OR (task_type = 'JOINT_SHARED' "
            "AND proposer_user_id IS NOT NULL AND recipient_user_id IS NULL) "
            "OR (task_type = 'AVENYTH_SUGGESTED' AND proposer_user_id IS NULL)",
            name="ck_workspace_tasks_type_participant_shape",
        ),
        Index("ix_workspace_tasks_workspace_id_status", "workspace_id", "status"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("relationship_workspaces.id", ondelete="CASCADE"), index=True
    )
    task_type: Mapped[TaskType] = mapped_column(String(30))
    status: Mapped[WorkspaceTaskStatus] = mapped_column(
        String(20), default=WorkspaceTaskStatus.PROPOSED
    )
    proposer_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    recipient_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Polymorph provenance pointer -- NOT a FK (no single source table). Only ever
    #: set together with prompt_version/knowledge_version, only for
    #: AVENYTH_SUGGESTED (see the CHECK constraint above).
    source_analysis_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    knowledge_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TaskAcceptance(Base):
    """PR-V2-07 -- append-only audit trail for one `WorkspaceTask` state
    transition, same shape/rationale as `ConsentEvent` for `ConsentGrant`
    (`actor_user_id` uses `ondelete=SET NULL` so history survives a deleted
    account)."""

    __tablename__ = "task_acceptances"

    id: Mapped[uuid.UUID] = _uuid_pk()
    task_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspace_tasks.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[TaskAcceptanceEventType] = mapped_column(String(20))
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    occurred_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


__all__ = [
    "AdminAuditEvent",
    "AnalysisJob",
    "Base",
    "Calculation",
    "CheckinAnalysis",
    "CheckinDimension",
    "CheckinResponse",
    "CheckinTemplate",
    "ConnectionInvitation",
    "ConsentEvent",
    "ConsentGrant",
    "EmailVerificationToken",
    "EntitlementAssignment",
    "EntitlementSet",
    "Export",
    "LLMGeneration",
    "NameIdentity",
    "PasswordResetToken",
    "Person",
    "PersonalTask",
    "PrivateNote",
    "PrivateReflection",
    "RelationshipAnalysis",
    "RelationshipCheckin",
    "RelationshipWorkspace",
    "Report",
    "ReportJob",
    "ReportSection",
    "RelationshipComparison",
    "ShadowDynamicsAnalysis",
    "Session",
    "TaskAcceptance",
    "User",
    "UserConnection",
    "WorkspaceMember",
    "WorkspaceTask",
]
