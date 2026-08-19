"""export file size and error code columns

Revision ID: e1728bd48eae
Revises: ffc969c9b8ad
Create Date: 2026-08-19 22:19:01.922861

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1728bd48eae"
down_revision: str | Sequence[str] | None = "ffc969c9b8ad"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("exports", sa.Column("file_size_bytes", sa.Integer(), nullable=True))
    op.add_column("exports", sa.Column("error_code", sa.String(length=80), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("exports", "error_code")
    op.drop_column("exports", "file_size_bytes")
