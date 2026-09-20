"""personal copilot thread index (PWA-06 / #123)

Revision ID: b9c0d1e2f3a4
Revises: e6a1b2c3d4e5
Create Date: 2026-09-21 00:00:00.000000

Adds the missing partial unique index for the `PERSONAL_PRIVATE` Copilot scope.

`chat_threads` already allows `scope = 'PERSONAL_PRIVATE'` with
`workspace_id IS NULL` (CHECK constraint `ck_chat_threads_scope_participant_shape`,
migration `f4a5b6c7d8e9`), and `RELATIONSHIP_SHARED`/`RELATIONSHIP_PRIVATE` each have
a partial unique index that makes their get-or-create idempotent under concurrency.
`PERSONAL_PRIVATE` had none -- and could not reuse one, because both existing indexes
lead with `workspace_id`, while a personal thread has `workspace_id IS NULL`. Without
this index a concurrent double-create (double-click, two tabs) can produce two
non-archived personal threads for one owner, so idempotency would rest on app-level
locking alone. Same `archived_at IS NULL` filter as the private-thread index: an
archived thread frees the slot, and a fresh create starts a new thread.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b9c0d1e2f3a4"
down_revision: str | Sequence[str] | None = "e6a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Purely additive -- one partial unique index, no table/column change.

    A personal thread carries `owner_user_id` and no `workspace_id`, so uniqueness
    on `(owner_user_id)` filtered to the personal scope is exactly the
    one-non-archived-personal-thread-per-owner invariant the create route needs.
    """
    op.create_index(
        "uq_chat_threads_one_personal_per_owner",
        "chat_threads",
        ["owner_user_id"],
        unique=True,
        postgresql_where=sa.text("scope = 'PERSONAL_PRIVATE' AND archived_at IS NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("uq_chat_threads_one_personal_per_owner", table_name="chat_threads")
