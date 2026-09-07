"""v2 email verification password reset entitlements

Revision ID: bd410b4e2a76
Revises: cd916a8c6edd
Create Date: 2026-09-07 15:16:53.192497

"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "bd410b4e2a76"
down_revision: str | Sequence[str] | None = "cd916a8c6edd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Deterministic (uuid5, not uuid4) so re-running this migration's seed logic against
#: the same namespace/name always yields the same id -- the seed INSERT itself still
#: only runs once per database (a fresh migration application), this only guarantees
#: which id it gets is reproducible across environments (dev/CI/prod all seed the
#: identical "beta_default" row id).
_BETA_DEFAULT_ENTITLEMENT_SET_ID = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://numra.app/entitlement-sets/beta_default"
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Grandfathering: every account that existed before email verification was
    # introduced counts as already verified (their own `created_at`) -- a newly added
    # gate condition must never lock out a pre-existing V1.6 user.
    op.execute(sa.text("UPDATE users SET email_verified_at = created_at"))

    op.create_table(
        "email_verification_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"]
    )
    op.create_index(
        "ix_email_verification_tokens_token_hash",
        "email_verification_tokens",
        ["token_hash"],
        unique=True,
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index(
        "ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True
    )

    op.create_table(
        "entitlement_sets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(60), nullable=False),
        sa.Column("personal_workspace", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("connections", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "relationship_workspaces", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("relationship_checkins", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("relationship_copilot", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "advanced_relationship_analysis",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column("life_tracking", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("premium_reports", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("max_connections", sa.Integer(), nullable=True),
        sa.Column("max_workspaces", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_entitlement_sets_key", "entitlement_sets", ["key"], unique=True)

    op.create_table(
        "entitlement_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "entitlement_set_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("entitlement_sets.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_entitlement_assignments_user_id", "entitlement_assignments", ["user_id"], unique=True
    )

    entitlement_sets_table = sa.table(
        "entitlement_sets",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("key", sa.String),
        sa.column("personal_workspace", sa.Boolean),
        sa.column("connections", sa.Boolean),
        sa.column("relationship_workspaces", sa.Boolean),
        sa.column("relationship_checkins", sa.Boolean),
        sa.column("relationship_copilot", sa.Boolean),
        sa.column("advanced_relationship_analysis", sa.Boolean),
        sa.column("life_tracking", sa.Boolean),
        sa.column("premium_reports", sa.Boolean),
        sa.column("max_connections", sa.Integer),
        sa.column("max_workspaces", sa.Integer),
    )
    op.bulk_insert(
        entitlement_sets_table,
        [
            {
                "id": _BETA_DEFAULT_ENTITLEMENT_SET_ID,
                "key": "beta_default",
                "personal_workspace": True,
                "connections": True,
                "relationship_workspaces": True,
                "relationship_checkins": True,
                "relationship_copilot": True,
                "advanced_relationship_analysis": True,
                "life_tracking": True,
                "premium_reports": True,
                "max_connections": None,
                "max_workspaces": None,
            }
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_entitlement_assignments_user_id", table_name="entitlement_assignments")
    op.drop_table("entitlement_assignments")
    op.drop_index("ix_entitlement_sets_key", table_name="entitlement_sets")
    op.drop_table("entitlement_sets")
    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_index("ix_email_verification_tokens_token_hash", table_name="email_verification_tokens")
    op.drop_index("ix_email_verification_tokens_user_id", table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")
    op.drop_column("users", "email_verified_at")
