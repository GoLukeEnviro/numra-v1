"""llm_generations: analysis_job_id/chat_message_id (Quellen analysis + copilot)

Revision ID: c5a9d3e72b16
Revises: 9d2f6b83a1c4
Create Date: 2026-10-07 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c5a9d3e72b16"
down_revision: str | Sequence[str] | None = "9d2f6b83a1c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Beide FKs sind ON DELETE CASCADE (Retention-Matrix): eine Zeile lebt
    genau so lange wie der Analyse-Job bzw. die Copilot-Nachricht, an der sie haengt. Die
    Bestandszeilen (Quelle report) behalten beide Spalten NULL.

    Fail fast statt Blockade: `lock_timeout` bricht die Migration bei Lock-Konflikt (z. B.
    laufender Worker mit offener Job-Transaktion) kontrolliert ab; sie ist transaktional und
    kann nach Beheben des Konflikts einfach wiederholt werden. Die FKs entstehen `NOT VALID`
    (kurzer Lock, kein Tabellenscan unter Lock) und werden danach validiert."""
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.add_column(
        "llm_generations", sa.Column("analysis_job_id", sa.Uuid(as_uuid=True), nullable=True)
    )
    op.add_column(
        "llm_generations", sa.Column("chat_message_id", sa.Uuid(as_uuid=True), nullable=True)
    )
    for column, parent in (
        ("analysis_job_id", "analysis_jobs"),
        ("chat_message_id", "chat_messages"),
    ):
        name = f"llm_generations_{column}_fkey"
        op.execute(
            f"ALTER TABLE llm_generations ADD CONSTRAINT {name} FOREIGN KEY ({column})"
            f" REFERENCES {parent} (id) ON DELETE CASCADE NOT VALID"
        )
        op.execute(f"ALTER TABLE llm_generations VALIDATE CONSTRAINT {name}")
    op.create_index(
        op.f("ix_llm_generations_analysis_job_id"),
        "llm_generations",
        ["analysis_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_llm_generations_chat_message_id"),
        "llm_generations",
        ["chat_message_id"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_llm_generations_single_ref",
        "llm_generations",
        "num_nonnulls(report_job_id, analysis_job_id, chat_message_id) <= 1",
    )


def downgrade() -> None:
    """Downgrade schema. Zeilen der Quellen analysis/copilot bleiben ohne Herkunftsbezug
    erhalten (die Spalten entfallen)."""
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.drop_constraint("ck_llm_generations_single_ref", "llm_generations", type_="check")
    op.drop_index(op.f("ix_llm_generations_chat_message_id"), table_name="llm_generations")
    op.drop_index(op.f("ix_llm_generations_analysis_job_id"), table_name="llm_generations")
    op.drop_constraint(
        "llm_generations_chat_message_id_fkey", "llm_generations", type_="foreignkey"
    )
    op.drop_constraint(
        "llm_generations_analysis_job_id_fkey", "llm_generations", type_="foreignkey"
    )
    op.drop_column("llm_generations", "chat_message_id")
    op.drop_column("llm_generations", "analysis_job_id")
