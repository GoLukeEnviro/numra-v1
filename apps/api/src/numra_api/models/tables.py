from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from numra_api.db import Base
from numra_api.models.enums import (
    ExportStatus,
    ExportType,
    NameIdentityKind,
    ReportJobStatus,
    ReportType,
    UserRole,
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

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
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


__all__ = [
    "AdminAuditEvent",
    "Base",
    "Calculation",
    "Export",
    "LLMGeneration",
    "NameIdentity",
    "Person",
    "Report",
    "ReportJob",
    "ReportSection",
    "RelationshipComparison",
    "Session",
    "User",
]
