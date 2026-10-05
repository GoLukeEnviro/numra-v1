"""feature_flags table

Revision ID: 04d4d6f4c5a0
Revises: b9c0d1e2f3a4
Create Date: 2026-10-04 18:01:34.536878

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "04d4d6f4c5a0"
down_revision: str | Sequence[str] | None = "b9c0d1e2f3a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "feature_flags",
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by_user_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("name"),
    )
    # Seed with the AVENYTH_*_ENABLED values actually live in production at
    # migration time (2026-10-04) -- NOT all-false -- so the DB-backed guard
    # (services/feature_flags.py) starts in the same state the env-var guard was
    # already in. See docs/planning/2026-10-04-admin-panel-flags-plan.md Task 1.
    feature_flags_table = sa.table(
        "feature_flags",
        sa.column("name", sa.String),
        sa.column("enabled", sa.Boolean),
    )
    op.bulk_insert(
        feature_flags_table,
        [
            {"name": "v2_master", "enabled": True},
            {"name": "connections", "enabled": True},
            {"name": "relationship_workspaces", "enabled": True},
            {"name": "checkins", "enabled": False},
            {"name": "tasks", "enabled": False},
            {"name": "copilot", "enabled": True},
            {"name": "evidence_layer", "enabled": False},
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("feature_flags")
