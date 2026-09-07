"""connections consent (invitations, user connections, relationship workspaces,
workspace members, consent grants, consent events)

Revision ID: b32b8d41f01b
Revises: c1a2b3d4e5f6
Create Date: 2026-09-07 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b32b8d41f01b"
down_revision: str | Sequence[str] | None = "c1a2b3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "connection_invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "inviter_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("invitee_email", sa.String(320), nullable=True),
        sa.Column("state", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "redeemed_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_connection_invitations_inviter_user_id",
        "connection_invitations",
        ["inviter_user_id"],
    )
    op.create_index(
        "ix_connection_invitations_token_hash",
        "connection_invitations",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_connection_invitations_invitee_email",
        "connection_invitations",
        ["invitee_email"],
    )

    op.create_table(
        "user_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_a_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_b_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("dissolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("user_a_id <> user_b_id", name="ck_user_connections_distinct_users"),
    )
    op.create_index("ix_user_connections_user_a_id", "user_connections", ["user_a_id"])
    op.create_index("ix_user_connections_user_b_id", "user_connections", ["user_b_id"])
    # Order-independent pairing guard -- prevents a duplicate connection between the
    # same two users regardless of which side is stored as A vs. B, DB-enforced
    # against races (see models/tables.py::UserConnection docstring).
    op.create_index(
        "uq_user_connections_pair",
        "user_connections",
        [sa.text("LEAST(user_a_id, user_b_id)"), sa.text("GREATEST(user_a_id, user_b_id)")],
        unique=True,
    )

    op.create_table(
        "relationship_workspaces",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("dissolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_relationship_workspaces_connection_id",
        "relationship_workspaces",
        ["connection_id"],
        unique=True,
    )

    op.create_table(
        "workspace_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "workspace_id", "user_id", name="uq_workspace_members_workspace_id_user_id"
        ),
    )
    op.create_index("ix_workspace_members_workspace_id", "workspace_members", ["workspace_id"])
    op.create_index("ix_workspace_members_user_id", "workspace_members", ["user_id"])

    op.create_table(
        "consent_grants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("relationship_workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "grantor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "grantee_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "grantor_user_id <> grantee_user_id", name="ck_consent_grants_distinct_users"
        ),
        sa.UniqueConstraint(
            "workspace_id",
            "grantor_user_id",
            "grantee_user_id",
            "scope",
            "version",
            name="uq_consent_grants_workspace_grantor_grantee_scope_version",
        ),
    )
    op.create_index("ix_consent_grants_workspace_id", "consent_grants", ["workspace_id"])
    op.create_index("ix_consent_grants_grantor_user_id", "consent_grants", ["grantor_user_id"])
    op.create_index("ix_consent_grants_grantee_user_id", "consent_grants", ["grantee_user_id"])

    op.create_table(
        "consent_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "grant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("consent_grants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(20), nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_consent_events_grant_id", "consent_events", ["grant_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_consent_events_grant_id", table_name="consent_events")
    op.drop_table("consent_events")

    op.drop_index("ix_consent_grants_grantee_user_id", table_name="consent_grants")
    op.drop_index("ix_consent_grants_grantor_user_id", table_name="consent_grants")
    op.drop_index("ix_consent_grants_workspace_id", table_name="consent_grants")
    op.drop_table("consent_grants")

    op.drop_index("ix_workspace_members_user_id", table_name="workspace_members")
    op.drop_index("ix_workspace_members_workspace_id", table_name="workspace_members")
    op.drop_table("workspace_members")

    op.drop_index("ix_relationship_workspaces_connection_id", table_name="relationship_workspaces")
    op.drop_table("relationship_workspaces")

    op.drop_index("uq_user_connections_pair", table_name="user_connections")
    op.drop_index("ix_user_connections_user_b_id", table_name="user_connections")
    op.drop_index("ix_user_connections_user_a_id", table_name="user_connections")
    op.drop_table("user_connections")

    op.drop_index("ix_connection_invitations_invitee_email", table_name="connection_invitations")
    op.drop_index("ix_connection_invitations_token_hash", table_name="connection_invitations")
    op.drop_index("ix_connection_invitations_inviter_user_id", table_name="connection_invitations")
    op.drop_table("connection_invitations")
