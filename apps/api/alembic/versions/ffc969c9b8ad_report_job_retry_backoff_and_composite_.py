"""report job retry backoff and composite idempotency key

Revision ID: ffc969c9b8ad
Revises: 4284dfff4331
Create Date: 2026-08-19 21:52:35.493243

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ffc969c9b8ad"
down_revision: str | Sequence[str] | None = "4284dfff4331"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "report_jobs", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "report_jobs", sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.drop_constraint(op.f("report_jobs_idempotency_key_key"), "report_jobs", type_="unique")
    op.create_unique_constraint(
        "uq_report_jobs_user_id_idempotency_key", "report_jobs", ["user_id", "idempotency_key"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_report_jobs_user_id_idempotency_key", "report_jobs", type_="unique")
    op.create_unique_constraint(
        op.f("report_jobs_idempotency_key_key"), "report_jobs", ["idempotency_key"]
    )
    op.drop_column("report_jobs", "last_error_at")
    op.drop_column("report_jobs", "next_attempt_at")
