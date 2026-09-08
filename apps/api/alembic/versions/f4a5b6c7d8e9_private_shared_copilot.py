"""private + shared copilot (PR-V2-09)

Revision ID: f4a5b6c7d8e9
Revises: e2f3a4b5c6d7
Create Date: 2026-09-08 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f4a5b6c7d8e9"
down_revision: str | Sequence[str] | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Purely additive -- four new tables, no changes to any existing table.

    Creation order matters for the FK chain: chat_threads -> thread_context_snapshots
    -> chat_messages (FKs to thread_context_snapshots) -> thread_summaries (FKs to
    chat_messages)."""
    op.create_table(
        "chat_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_workspaces.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "owner_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("scope", sa.String(24), nullable=False),
        sa.Column("context_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(scope = 'RELATIONSHIP_SHARED' AND workspace_id IS NOT NULL "
            "AND owner_user_id IS NULL) "
            "OR (scope = 'RELATIONSHIP_PRIVATE' AND workspace_id IS NOT NULL "
            "AND owner_user_id IS NOT NULL) "
            "OR (scope = 'PERSONAL_PRIVATE' AND workspace_id IS NULL "
            "AND owner_user_id IS NOT NULL)",
            name="ck_chat_threads_scope_participant_shape",
        ),
    )
    op.create_index("ix_chat_threads_workspace_id", "chat_threads", ["workspace_id"])
    op.create_index("ix_chat_threads_owner_user_id", "chat_threads", ["owner_user_id"])
    op.create_index("ix_chat_threads_workspace_id_scope", "chat_threads", ["workspace_id", "scope"])
    op.create_index(
        "uq_chat_threads_one_shared_per_workspace",
        "chat_threads",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("scope = 'RELATIONSHIP_SHARED' AND archived_at IS NULL"),
    )
    op.create_index(
        "uq_chat_threads_one_private_per_owner",
        "chat_threads",
        ["workspace_id", "owner_user_id"],
        unique=True,
        postgresql_where=sa.text("scope = 'RELATIONSHIP_PRIVATE' AND archived_at IS NULL"),
    )

    op.create_table(
        "thread_context_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "requester_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(24), nullable=False),
        sa.Column("context_version", sa.Integer(), nullable=False),
        sa.Column("context_blocks_json", postgresql.JSONB(), nullable=False),
        sa.Column("consent_scopes_checked", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_thread_context_snapshots_thread_id", "thread_context_snapshots", ["thread_id"]
    )
    op.create_index(
        "ix_thread_context_snapshots_requester_user_id",
        "thread_context_snapshots",
        ["requester_user_id"],
    )
    op.create_index(
        "ix_thread_context_snapshots_thread_id_created_at",
        "thread_context_snapshots",
        ["thread_id", "created_at"],
    )

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column(
            "author_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("basis_type", sa.String(24), nullable=True),
        sa.Column("prompt_version", sa.String(40), nullable=True),
        sa.Column("knowledge_version", sa.String(40), nullable=True),
        sa.Column(
            "context_snapshot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("thread_context_snapshots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("model_provider", sa.String(40), nullable=True),
        sa.Column("model_name", sa.String(80), nullable=True),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_chat_messages_thread_id", "chat_messages", ["thread_id"])
    op.create_index(
        "ix_chat_messages_thread_id_created_at", "chat_messages", ["thread_id", "created_at"]
    )

    op.create_table(
        "thread_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(24), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column(
            "covers_up_to_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("context_version", sa.Integer(), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_thread_summaries_thread_id", "thread_summaries", ["thread_id"])
    op.create_index(
        "ix_thread_summaries_thread_id_created_at", "thread_summaries", ["thread_id", "created_at"]
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_thread_summaries_thread_id_created_at", table_name="thread_summaries")
    op.drop_index("ix_thread_summaries_thread_id", table_name="thread_summaries")
    op.drop_table("thread_summaries")

    op.drop_index("ix_chat_messages_thread_id_created_at", table_name="chat_messages")
    op.drop_index("ix_chat_messages_thread_id", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index(
        "ix_thread_context_snapshots_thread_id_created_at", table_name="thread_context_snapshots"
    )
    op.drop_index(
        "ix_thread_context_snapshots_requester_user_id", table_name="thread_context_snapshots"
    )
    op.drop_index("ix_thread_context_snapshots_thread_id", table_name="thread_context_snapshots")
    op.drop_table("thread_context_snapshots")

    op.drop_index("uq_chat_threads_one_private_per_owner", table_name="chat_threads")
    op.drop_index("uq_chat_threads_one_shared_per_workspace", table_name="chat_threads")
    op.drop_index("ix_chat_threads_workspace_id_scope", table_name="chat_threads")
    op.drop_index("ix_chat_threads_owner_user_id", table_name="chat_threads")
    op.drop_index("ix_chat_threads_workspace_id", table_name="chat_threads")
    op.drop_table("chat_threads")
