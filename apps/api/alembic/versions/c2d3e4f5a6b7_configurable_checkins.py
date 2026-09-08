"""configurable check-ins (PR-V2-06)

Revision ID: c2d3e4f5a6b7
Revises: b7c8d9e0f1a2
Create Date: 2026-09-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: str | Sequence[str] | None = "b7c8d9e0f1a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Purely additive -- no backfill needed (see specs/v2/checkin-
    spec.md, checkin templates are lazily created on first access, not eagerly for
    existing workspaces)."""
    op.create_table(
        "checkin_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "workspace_id", "version", name="uq_checkin_templates_workspace_version"
        ),
    )
    op.create_index("ix_checkin_templates_workspace_id", "checkin_templates", ["workspace_id"])

    op.create_table(
        "checkin_dimensions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("semantic_key", sa.String(60), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scale_min", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("scale_max", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "workspace_id", "semantic_key", name="uq_checkin_dimensions_workspace_semantic_key"
        ),
        sa.CheckConstraint("scale_min < scale_max", name="ck_checkin_dimensions_scale_min_lt_max"),
    )
    op.create_index("ix_checkin_dimensions_workspace_id", "checkin_dimensions", ["workspace_id"])

    op.create_table(
        "relationship_checkins",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checkin_template_version", sa.Integer(), nullable=False),
        sa.Column(
            "cycle_started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="AWAITING_SUBMISSIONS"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_relationship_checkins_workspace_id", "relationship_checkins", ["workspace_id"]
    )
    # Race-safety net: two members submitting their first response for a new round at
    # (near-)the same time would otherwise each create their own AWAITING_SUBMISSIONS
    # round under READ COMMITTED (neither sees the other's uncommitted INSERT), so the
    # two submissions never land on the same round and the analysis never triggers.
    op.create_index(
        "uq_relationship_checkins_one_awaiting_per_workspace",
        "relationship_checkins",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("status = 'AWAITING_SUBMISSIONS'"),
    )

    op.create_table(
        "checkin_responses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "checkin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_checkins.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "dimension_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("checkin_dimensions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("semantic_key", sa.String(60), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "checkin_id",
            "user_id",
            "dimension_id",
            name="uq_checkin_responses_checkin_user_dimension",
        ),
    )
    op.create_index("ix_checkin_responses_checkin_id", "checkin_responses", ["checkin_id"])
    op.create_index("ix_checkin_responses_user_id", "checkin_responses", ["user_id"])

    op.create_table(
        "checkin_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "checkin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_checkins.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("checkin_template_version", sa.Integer(), nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_checkin_analyses_workspace_id", "checkin_analyses", ["workspace_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_checkin_analyses_workspace_id", table_name="checkin_analyses")
    op.drop_table("checkin_analyses")

    op.drop_index("ix_checkin_responses_user_id", table_name="checkin_responses")
    op.drop_index("ix_checkin_responses_checkin_id", table_name="checkin_responses")
    op.drop_table("checkin_responses")

    op.drop_index(
        "uq_relationship_checkins_one_awaiting_per_workspace",
        table_name="relationship_checkins",
    )
    op.drop_index("ix_relationship_checkins_workspace_id", table_name="relationship_checkins")
    op.drop_table("relationship_checkins")

    op.drop_index("ix_checkin_dimensions_workspace_id", table_name="checkin_dimensions")
    op.drop_table("checkin_dimensions")

    op.drop_index("ix_checkin_templates_workspace_id", table_name="checkin_templates")
    op.drop_table("checkin_templates")
