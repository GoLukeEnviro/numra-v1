"""llm_generations: source/attempt/token columns, status+source checks

Revision ID: 9d2f6b83a1c4
Revises: 7c3e9a51b2d8
Create Date: 2026-10-06 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9d2f6b83a1c4"
down_revision: str | Sequence[str] | None = "7c3e9a51b2d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Bestehende Zeilen (der Writer ist neu, es gibt praktisch keine)
    stammen aus dem Report-Pfad: source='report', attempt=1, status kleingeschrieben."""
    op.add_column(
        "llm_generations",
        sa.Column("source", sa.String(length=20), nullable=False, server_default="report"),
    )
    op.alter_column("llm_generations", "source", server_default=None)
    op.add_column(
        "llm_generations",
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("llm_generations", sa.Column("prompt_tokens", sa.Integer(), nullable=True))
    op.add_column("llm_generations", sa.Column("completion_tokens", sa.Integer(), nullable=True))
    op.add_column("llm_generations", sa.Column("total_tokens", sa.Integer(), nullable=True))
    op.drop_column("llm_generations", "token_usage")
    # Bestandswerte normalisieren; alles Unbekannte ('success', 'failed', ...) wird 'error',
    # damit der CHECK auf einer Bestands-DB nie scheitert.
    op.execute("UPDATE llm_generations SET status = lower(status)")
    op.execute(
        "UPDATE llm_generations SET status = 'error' WHERE status NOT IN ('ok', 'error', 'retry')"
    )
    op.create_check_constraint(
        "ck_llm_generations_source",
        "llm_generations",
        "source IN ('report', 'analysis', 'copilot')",
    )
    op.create_check_constraint(
        "ck_llm_generations_status",
        "llm_generations",
        "status IN ('ok', 'error', 'retry')",
    )
    op.create_check_constraint("ck_llm_generations_attempt", "llm_generations", "attempt >= 1")


def downgrade() -> None:
    """Downgrade schema. Die Token-Zahlen gehen verloren (kein Rueckweg in das JSONB)."""
    op.drop_constraint("ck_llm_generations_attempt", "llm_generations", type_="check")
    op.drop_constraint("ck_llm_generations_status", "llm_generations", type_="check")
    op.drop_constraint("ck_llm_generations_source", "llm_generations", type_="check")
    op.add_column(
        "llm_generations",
        sa.Column("token_usage", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.drop_column("llm_generations", "total_tokens")
    op.drop_column("llm_generations", "completion_tokens")
    op.drop_column("llm_generations", "prompt_tokens")
    op.drop_column("llm_generations", "attempt")
    op.drop_column("llm_generations", "source")
