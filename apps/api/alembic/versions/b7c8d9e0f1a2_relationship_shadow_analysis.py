"""relationship/shadow-dynamics analysis (PR-V2-05)

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f7
Create Date: 2026-09-07 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7c8d9e0f1a2"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "analysis_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requested_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("analysis_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="QUEUED"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(60), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )
    op.create_index("ix_analysis_jobs_workspace_id", "analysis_jobs", ["workspace_id"])
    op.create_index(
        "ix_analysis_jobs_requested_by_user_id", "analysis_jobs", ["requested_by_user_id"]
    )
    # Partial unique index -- same pattern as ReportJob's
    # `uq_report_jobs_user_id_idempotency_key`, but scoped to only non-NULL
    # idempotency keys (Context7-verified: postgresql_where kwarg on op.create_index,
    # see a1b2c3d4e5f7's `uq_people_user_id_self_mode` for the identical pattern in
    # this repo) so multiple jobs without a client-supplied key never collide.
    op.create_index(
        "uq_analysis_jobs_user_id_idempotency_key",
        "analysis_jobs",
        ["requested_by_user_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    op.create_table(
        "relationship_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("relationship_type", sa.String(20), nullable=False),
        sa.Column(
            "calculation_a_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calculations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "calculation_b_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calculations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("calculation_version", sa.String(20), nullable=False),
        sa.Column("knowledge_version", sa.String(20), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("model_provider", sa.String(60), nullable=True),
        sa.Column("model_name", sa.String(120), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("result_json", postgresql.JSONB(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_relationship_analyses_workspace_id", "relationship_analyses", ["workspace_id"]
    )

    op.create_table(
        "shadow_dynamics_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("relationship_type", sa.String(20), nullable=False),
        sa.Column(
            "calculation_a_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calculations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "calculation_b_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calculations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("calculation_version", sa.String(20), nullable=False),
        sa.Column("knowledge_version", sa.String(20), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("model_provider", sa.String(60), nullable=True),
        sa.Column("model_name", sa.String(120), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("result_json", postgresql.JSONB(), nullable=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_shadow_dynamics_analyses_workspace_id", "shadow_dynamics_analyses", ["workspace_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_shadow_dynamics_analyses_workspace_id", table_name="shadow_dynamics_analyses")
    op.drop_table("shadow_dynamics_analyses")

    op.drop_index("ix_relationship_analyses_workspace_id", table_name="relationship_analyses")
    op.drop_table("relationship_analyses")

    op.drop_index("uq_analysis_jobs_user_id_idempotency_key", table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_requested_by_user_id", table_name="analysis_jobs")
    op.drop_index("ix_analysis_jobs_workspace_id", table_name="analysis_jobs")
    op.drop_table("analysis_jobs")
