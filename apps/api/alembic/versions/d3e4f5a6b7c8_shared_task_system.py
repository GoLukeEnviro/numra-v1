"""shared task system (PR-V2-07)

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-09-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d3e4f5a6b7c8"
down_revision: str | Sequence[str] | None = "c2d3e4f5a6b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Purely additive -- personal_tasks is untouched (specs/v2/
    data-model.md: PersonalTask stays its own slim table)."""
    op.create_table(
        "workspace_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_type", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PROPOSED"),
        sa.Column(
            "proposer_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "recipient_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_analysis_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("prompt_version", sa.String(20), nullable=True),
        sa.Column("knowledge_version", sa.String(20), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "task_type = 'AVENYTH_SUGGESTED' OR "
            "(source_analysis_id IS NULL AND prompt_version IS NULL "
            "AND knowledge_version IS NULL)",
            name="ck_workspace_tasks_provenance_only_avenyth_suggested",
        ),
        sa.CheckConstraint(
            "(task_type = 'FOR_PARTNER_PROPOSED' "
            "AND proposer_user_id IS NOT NULL AND recipient_user_id IS NOT NULL) "
            "OR (task_type = 'JOINT_SHARED' "
            "AND proposer_user_id IS NOT NULL AND recipient_user_id IS NULL) "
            "OR (task_type = 'AVENYTH_SUGGESTED' AND proposer_user_id IS NULL)",
            name="ck_workspace_tasks_type_participant_shape",
        ),
    )
    op.create_index("ix_workspace_tasks_workspace_id", "workspace_tasks", ["workspace_id"])
    op.create_index("ix_workspace_tasks_proposer_user_id", "workspace_tasks", ["proposer_user_id"])
    op.create_index(
        "ix_workspace_tasks_recipient_user_id", "workspace_tasks", ["recipient_user_id"]
    )
    op.create_index(
        "ix_workspace_tasks_workspace_id_status", "workspace_tasks", ["workspace_id", "status"]
    )

    op.create_table(
        "task_acceptances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "task_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspace_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_task_acceptances_task_id", "task_acceptances", ["task_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_task_acceptances_task_id", table_name="task_acceptances")
    op.drop_table("task_acceptances")

    op.drop_index("ix_workspace_tasks_workspace_id_status", table_name="workspace_tasks")
    op.drop_index("ix_workspace_tasks_recipient_user_id", table_name="workspace_tasks")
    op.drop_index("ix_workspace_tasks_proposer_user_id", table_name="workspace_tasks")
    op.drop_index("ix_workspace_tasks_workspace_id", table_name="workspace_tasks")
    op.drop_table("workspace_tasks")
