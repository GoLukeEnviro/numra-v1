"""feature_flag_bootstrap singleton table

Revision ID: 7c3e9a51b2d8
Revises: 04d4d6f4c5a0
Create Date: 2026-10-06 17:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c3e9a51b2d8"
down_revision: str | Sequence[str] | None = "04d4d6f4c5a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "feature_flag_bootstrap",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "initialized_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("profile", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_feature_flag_bootstrap_singleton"),
        sa.CheckConstraint(
            "source IN ('bootstrap', 'adopted')", name="ck_feature_flag_bootstrap_source"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Bestandsdatenbank: vorhandene Flag-Zeilen sind die gelebte Wahrheit. Nur den
    # Status anlegen (adopted) -- feature_flags selbst wird NICHT angefasst, damit
    # Werte und updated_at bitgleich bleiben und `flags init` zum No-op wird.
    op.execute(
        "INSERT INTO feature_flag_bootstrap (id, profile, source) "
        "SELECT 1, 'pre-existing', 'adopted' WHERE EXISTS (SELECT 1 FROM feature_flags)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("feature_flag_bootstrap")
