"""relationship insights column

Revision ID: 18f0d1efc735
Revises: e1728bd48eae
Create Date: 2026-08-22 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "18f0d1efc735"
down_revision: str | Sequence[str] | None = "e1728bd48eae"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "relationships",
        sa.Column(
            "insights_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("relationships", "insights_json")
