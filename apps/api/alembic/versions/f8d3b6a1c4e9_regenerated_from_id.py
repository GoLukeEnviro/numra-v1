"""regenerated_from_id: verknuepfte Neuerzeugung von Berichten und Beziehungsanalysen (D6)

Revision ID: f8d3b6a1c4e9
Revises: e5b7d1a9c3f2
Create Date: 2026-10-10 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f8d3b6a1c4e9"
down_revision: str | Sequence[str] | None = "e5b7d1a9c3f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LIVE = "regenerated_from_id IS NOT NULL AND status <> 'FAILED'"


def upgrade() -> None:
    """Upgrade schema. Rein additiv: zwei nullbare Spalten (Metadaten-Aenderung, kein
    Rewrite) und zwei partielle Unique-Indizes, die auf leere Spalten greifen. Der alte
    Code liest und schreibt die Spalten nicht; bestehende Zeilen behalten NULL."""
    op.execute("SET LOCAL lock_timeout = '5s'")
    for table, index in (
        ("reports", "uq_reports_live_regeneration"),
        ("relationship_analyses", "uq_relationship_analyses_live_regeneration"),
    ):
        op.add_column(
            table,
            sa.Column(
                "regenerated_from_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey(f"{table}.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )
        op.create_index(
            index,
            table,
            ["regenerated_from_id"],
            unique=True,
            postgresql_where=sa.text(_LIVE),
        )


def downgrade() -> None:
    """Downgrade schema (nur der Vollstaendigkeit halber; das Projekt faehrt kein
    `alembic downgrade`)."""
    op.execute("SET LOCAL lock_timeout = '5s'")
    for table, index in (
        ("relationship_analyses", "uq_relationship_analyses_live_regeneration"),
        ("reports", "uq_reports_live_regeneration"),
    ):
        op.drop_index(index, table_name=table)
        op.drop_column(table, "regenerated_from_id")
