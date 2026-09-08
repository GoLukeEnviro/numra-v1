"""dissolution + account deletion (PR-V2-10)

Revision ID: a1b2c3d4e5f6
Revises: f4a5b6c7d8e9
Create Date: 2026-09-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f4a5b6c7d8e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Purely additive -- two new nullable columns on `users`, no changes to any
    other table. `relationship_workspaces.dissolved_at` already exists since
    PR-V2-03 and needs no migration here."""
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("display_name_override", sa.String(120), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "display_name_override")
    op.drop_column("users", "deleted_at")
