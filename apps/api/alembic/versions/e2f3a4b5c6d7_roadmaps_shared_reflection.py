"""roadmaps + shared reflection (PR-V2-08)

Revision ID: e2f3a4b5c6d7
Revises: d3e4f5a6b7c8
Create Date: 2026-09-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e2f3a4b5c6d7"
down_revision: str | Sequence[str] | None = "d3e4f5a6b7c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Purely additive -- workspace_tasks only gains the nullable
    roadmap_milestone_id column."""
    op.create_table(
        "relationship_roadmaps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("roadmap_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PROPOSED"),
        sa.Column(
            "proposer_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
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
            "proposer_user_id IS NULL OR "
            "(source_analysis_id IS NULL AND prompt_version IS NULL "
            "AND knowledge_version IS NULL)",
            name="ck_relationship_roadmaps_provenance_only_avenyth_suggested",
        ),
    )
    op.create_index(
        "ix_relationship_roadmaps_workspace_id", "relationship_roadmaps", ["workspace_id"]
    )
    op.create_index(
        "ix_relationship_roadmaps_proposer_user_id", "relationship_roadmaps", ["proposer_user_id"]
    )
    op.create_index(
        "ix_relationship_roadmaps_workspace_id_status",
        "relationship_roadmaps",
        ["workspace_id", "status"],
    )

    op.create_table(
        "roadmap_milestones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "roadmap_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_roadmaps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("milestone_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_date", sa.Date(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_roadmap_milestones_roadmap_id", "roadmap_milestones", ["roadmap_id"])
    op.create_index(
        "ix_roadmap_milestones_roadmap_id_sequence",
        "roadmap_milestones",
        ["roadmap_id", "sequence"],
    )

    op.create_table(
        "shared_reflections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_private_reflection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("private_reflections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "shared_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_shared_reflections_workspace_id", "shared_reflections", ["workspace_id"])
    op.create_index(
        "ix_shared_reflections_author_user_id", "shared_reflections", ["author_user_id"]
    )
    op.create_index(
        "ix_shared_reflections_source_private_reflection_id",
        "shared_reflections",
        ["source_private_reflection_id"],
    )

    op.add_column(
        "workspace_tasks",
        sa.Column(
            "roadmap_milestone_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("roadmap_milestones.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_workspace_tasks_roadmap_milestone_id", "workspace_tasks", ["roadmap_milestone_id"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_workspace_tasks_roadmap_milestone_id", table_name="workspace_tasks")
    op.drop_column("workspace_tasks", "roadmap_milestone_id")

    op.drop_index(
        "ix_shared_reflections_source_private_reflection_id", table_name="shared_reflections"
    )
    op.drop_index("ix_shared_reflections_author_user_id", table_name="shared_reflections")
    op.drop_index("ix_shared_reflections_workspace_id", table_name="shared_reflections")
    op.drop_table("shared_reflections")

    op.drop_index("ix_roadmap_milestones_roadmap_id_sequence", table_name="roadmap_milestones")
    op.drop_index("ix_roadmap_milestones_roadmap_id", table_name="roadmap_milestones")
    op.drop_table("roadmap_milestones")

    op.drop_index(
        "ix_relationship_roadmaps_workspace_id_status", table_name="relationship_roadmaps"
    )
    op.drop_index("ix_relationship_roadmaps_proposer_user_id", table_name="relationship_roadmaps")
    op.drop_index("ix_relationship_roadmaps_workspace_id", table_name="relationship_roadmaps")
    op.drop_table("relationship_roadmaps")
