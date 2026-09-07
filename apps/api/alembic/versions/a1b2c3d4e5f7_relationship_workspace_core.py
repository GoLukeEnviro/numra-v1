"""relationship workspace core (person_account_mode backfill + relationship_type)

Revision ID: a1b2c3d4e5f7
Revises: b32b8d41f01b
Create Date: 2026-09-07 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: str | Sequence[str] | None = "b32b8d41f01b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1) Add the column nullable-safe via server_default -- every existing row is
    # provisionally SELF until the backfill below re-derives the true value per
    # user_id (specs/v2/minor-profile-policy.md).
    op.add_column(
        "people",
        sa.Column("person_account_mode", sa.String(20), nullable=False, server_default="SELF"),
    )

    # 2) Backfill in reine SQL (kein ORM-Laden) -- pro user_id wird die aelteste
    # Person-Zeile (created_at ASC, id ASC als Tie-Breaker) als SELF markiert, alle
    # weiteren als MANAGED_OTHER. Muss VOR dem Partial-Unique-Index laufen, sonst
    # scheitert der Index-Build am Zwischenzustand mit mehreren SELF-Zeilen pro
    # user_id (Context7-verified: op.execute() fuer rohe SQL-Statements, siehe
    # alembic.sqlalchemy.org/en/latest/ops.html#execute).
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY user_id ORDER BY created_at ASC, id ASC
                   ) AS rn
            FROM people
        )
        UPDATE people
        SET person_account_mode = CASE WHEN ranked.rn = 1 THEN 'SELF' ELSE 'MANAGED_OTHER' END
        FROM ranked
        WHERE people.id = ranked.id
        """
    )

    # 3) Erst jetzt der Partial-Unique-Index -- garantiert nach dem Backfill genau
    # eine SELF-Zeile pro user_id (Context7-verified: postgresql_where kwarg auf
    # op.create_index, siehe docs.sqlalchemy.org/en/20/core/constraints.html).
    op.create_index(
        "uq_people_user_id_self_mode",
        "people",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("person_account_mode = 'SELF'"),
    )

    op.add_column(
        "relationship_workspaces",
        sa.Column("relationship_type", sa.String(20), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("relationship_workspaces", "relationship_type")

    op.drop_index("uq_people_user_id_self_mode", table_name="people")
    op.drop_column("people", "person_account_mode")
