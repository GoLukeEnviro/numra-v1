"""retain shared relationship/shadow analyses after account deletion (PR-V2-10)

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-09-08 01:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("calculation_a_id", "calculation_b_id")
_TABLES = ("relationship_analyses", "shadow_dynamics_analyses")


def upgrade() -> None:
    """`RelationshipAnalysis`/`ShadowDynamicsAnalysis` sind laut
    specs/v2/dissolution-policy.md ("What is retained read-only") fuer BEIDE
    ehemaligen Teilnehmer lesbar, auch nachdem einer seinen Account (und damit seine
    `Person`/`Calculation`-Rows) geloescht hat. Mit CASCADE riss die geteilte Zeile
    selbst mit -- SET NULL laesst sie ueberleben (`result_json` traegt die vollstaendige
    Analyse bereits unabhaengig, die Calculation-Referenz ist reine Provenienz).
    Exakt das etablierte `ChatMessage.author_user_id`-Pattern."""
    for table in _TABLES:
        for column in _COLUMNS:
            op.drop_constraint(f"{table}_{column}_fkey", table, type_="foreignkey")
            op.alter_column(table, column, nullable=True)
            op.create_foreign_key(
                f"{table}_{column}_fkey",
                table,
                "calculations",
                [column],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    """Downgrade-Risiko: Zeilen, deren `calculation_a_id`/`calculation_b_id` bereits
    durch eine zwischenzeitliche Account-Loeschung auf NULL gesetzt wurden, lassen sich
    hier nicht wieder befuellen -- `alter_column(nullable=False)` schlaegt dann mit
    einer NOT-NULL-Verletzung fehl. Akzeptiertes, dokumentiertes Downgrade-Risiko dieser
    Migration."""
    for table in reversed(_TABLES):
        for column in reversed(_COLUMNS):
            op.drop_constraint(f"{table}_{column}_fkey", table, type_="foreignkey")
            op.alter_column(table, column, nullable=False)
            op.create_foreign_key(
                f"{table}_{column}_fkey",
                table,
                "calculations",
                [column],
                ["id"],
                ondelete="CASCADE",
            )
