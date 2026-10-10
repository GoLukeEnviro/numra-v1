"""users: age_confirmed_at/age_declaration_version (D2, 18+-Erklaerung)

Revision ID: d2a8c4f6b1e3
Revises: c5a9d3e72b16
Create Date: 2026-10-09 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2a8c4f6b1e3"
down_revision: str | Sequence[str] | None = "c5a9d3e72b16"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Zwei additive, nullable Spalten ohne Default: Metadaten-Aenderung
    ohne Tabellen-Rewrite, vom alten Code ignoriert (der kennt die Spalten nicht und
    schreibt sie nicht). Bestandskonten behalten NULL = NICHT bestaetigt -- bewusst kein
    Backfill."""
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column("users", sa.Column("age_confirmed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users", sa.Column("age_declaration_version", sa.String(length=40), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema (nur der Vollstaendigkeit halber; das Projekt faehrt kein
    `alembic downgrade`)."""
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.drop_column("users", "age_declaration_version")
    op.drop_column("users", "age_confirmed_at")
