"""usage_reservations: Quota-Ledger fuer kostenintensive Funktionen (D4)

Revision ID: e5b7d1a9c3f2
Revises: d2a8c4f6b1e3
Create Date: 2026-10-10 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e5b7d1a9c3f2"
down_revision: str | Sequence[str] | None = "d2a8c4f6b1e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Rein additiv: eine neue, leere Tabelle, die vom alten Code nicht
    gelesen wird. Ohne gesetzte Limits (Default) schreibt der neue Code keine Zeilen --
    ein Rollback auf den alten Code laesst die Tabelle ungenutzt liegen."""
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.create_table(
        "usage_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("feature", sa.String(20), nullable=False),
        sa.Column("ref_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("feature", "ref_id", name="uq_usage_reservations_feature_ref_id"),
    )
    op.create_index(
        "ix_usage_reservations_user_feature_created",
        "usage_reservations",
        ["user_id", "feature", "created_at"],
    )


def downgrade() -> None:
    """Downgrade schema (nur der Vollstaendigkeit halber; das Projekt faehrt kein
    `alembic downgrade`)."""
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.drop_index("ix_usage_reservations_user_feature_created", table_name="usage_reservations")
    op.drop_table("usage_reservations")
