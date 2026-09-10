"""WEB-06a: immutable rounds, versioned dimensions and atomic request identity.

Preflight is deliberately conservative: no repair or private values in diagnostics.
PostgreSQL transactional DDL ensures any failure also rolls back the Alembic stamp.
"""

from collections import defaultdict
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "e6a1b2c3d4e5"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _preflight() -> None:
    db = op.get_bind()
    # No concurrent old application may change the inspected rows during migration.
    db.execute(
        sa.text(
            "LOCK TABLE relationship_workspaces, checkin_templates, "
            "checkin_dimensions, relationship_checkins, checkin_responses, "
            "checkin_analyses IN SHARE ROW EXCLUSIVE MODE"
        )
    )
    rounds = (
        db.execute(
            sa.text(
                "SELECT id, workspace_id, checkin_template_version FROM relationship_checkins "
                "WHERE status = 'AWAITING_SUBMISSIONS'"
            )
        )
        .mappings()
        .all()
    )
    invalid = 0
    for r in rounds:
        params = {
            "workspace": r["workspace_id"],
            "version": r["checkin_template_version"],
            "round": r["id"],
        }
        template_count = db.execute(
            sa.text(
                "SELECT count(*) FROM checkin_templates WHERE workspace_id=:workspace "
                "AND version=:version AND active"
            ),
            params,
        ).scalar_one()
        dims = (
            db.execute(
                sa.text(
                    "SELECT id, semantic_key, scale_min, scale_max FROM checkin_dimensions "
                    "WHERE workspace_id=:workspace AND template_version=:version AND active"
                ),
                params,
            )
            .mappings()
            .all()
        )
        by_id = {d["id"]: d for d in dims}
        responses = (
            db.execute(
                sa.text(
                    "SELECT user_id, dimension_id, semantic_key, value FROM checkin_responses "
                    "WHERE checkin_id=:round"
                ),
                params,
            )
            .mappings()
            .all()
        )
        analysis_count = db.execute(
            sa.text("SELECT count(*) FROM checkin_analyses WHERE checkin_id=:round"), params
        ).scalar_one()
        members = set(
            db.execute(
                sa.text(
                    "SELECT user_id FROM workspace_members "
                    "WHERE workspace_id=:workspace AND status='ACTIVE'"
                ),
                params,
            ).scalars()
        )
        groups: dict[object, list[object]] = defaultdict(list)
        bad = template_count != 1 or not dims or analysis_count != 0 or len(members) != 2
        for answer in responses:
            groups[answer["user_id"]].append(answer["dimension_id"])
            d = by_id.get(answer["dimension_id"])
            if (
                d is None
                or answer["semantic_key"] != d["semantic_key"]
                or not d["scale_min"] <= answer["value"] <= d["scale_max"]
                or answer["user_id"] not in members
            ):
                bad = True
        if len(groups) > 1:
            bad = True  # Both submitted but no analysis: never silently repair history.
        for ids in groups.values():
            if len(ids) != len(set(ids)) or set(ids) != set(by_id):
                bad = True
        invalid += int(bad)
    duplicates = db.execute(
        sa.text(
            "SELECT count(*) FROM (SELECT workspace_id FROM checkin_templates WHERE active "
            "GROUP BY workspace_id HAVING count(*) > 1) AS invalid"
        )
    ).scalar_one()
    if invalid or duplicates:
        raise RuntimeError(
            "CHECKIN_MIGRATION_INCOMPATIBLE: "
            f"{invalid} open rounds; {duplicates} active-template conflicts. "
            "No data changed. Preserve originals; see WEB-06a migration procedure."
        )


def upgrade() -> None:
    _preflight()
    op.add_column("checkin_dimensions", sa.Column("dimension_class", sa.String(20), nullable=True))
    op.execute(
        "UPDATE checkin_dimensions SET dimension_class='INTIMATE' "
        "WHERE semantic_key='sexual_connection'"
    )
    op.drop_constraint(
        "uq_checkin_dimensions_workspace_semantic_key", "checkin_dimensions", type_="unique"
    )
    op.create_unique_constraint(
        "uq_checkin_dimensions_workspace_version_key",
        "checkin_dimensions",
        ["workspace_id", "template_version", "semantic_key"],
    )
    op.create_index(
        "uq_checkin_templates_active",
        "checkin_templates",
        ["workspace_id"],
        unique=True,
        postgresql_where=sa.text("active"),
    )
    op.add_column(
        "relationship_checkins",
        sa.Column(
            "snapshot_origin", sa.String(20), nullable=False, server_default="LEGACY_MISSING"
        ),
    )
    op.create_table(
        "checkin_round_dimensions",
        sa.Column(
            "checkin_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("relationship_checkins.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        # Retain snapshot and identifier; prohibit deleting referenced configuration.
        sa.Column(
            "dimension_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey(
                "checkin_dimensions.id", ondelete="NO ACTION", deferrable=True, initially="DEFERRED"
            ),
            primary_key=True,
        ),
        sa.Column("semantic_key", sa.String(60), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scale_min", sa.Integer(), nullable=False),
        sa.Column("scale_max", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    op.create_table(
        "checkin_idempotency",
        sa.Column(
            "workspace_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("relationship_workspaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("operation", sa.String(20), primary_key=True),
        sa.Column("key", sa.String(200), primary_key=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column(
            "checkin_id",
            pg.UUID(as_uuid=True),
            sa.ForeignKey("relationship_checkins.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )
    op.drop_constraint(
        "checkin_responses_dimension_id_fkey", "checkin_responses", type_="foreignkey"
    )
    op.create_foreign_key(
        "checkin_responses_dimension_id_fkey",
        "checkin_responses",
        "checkin_dimensions",
        ["dimension_id"],
        ["id"],
        ondelete="NO ACTION",
        deferrable=True,
        initially="DEFERRED",
    )
    op.execute(
        "INSERT INTO checkin_round_dimensions "
        "(checkin_id, dimension_id, semantic_key, label, description, scale_min, "
        "scale_max, sort_order) SELECT r.id, d.id, d.semantic_key, d.label, d.description, "
        "d.scale_min, d.scale_max, d.sort_order FROM relationship_checkins r "
        "JOIN checkin_dimensions d ON d.workspace_id=r.workspace_id "
        "AND d.template_version=r.checkin_template_version AND d.active "
        "WHERE r.status='AWAITING_SUBMISSIONS'"
    )
    op.execute(
        "UPDATE relationship_checkins SET snapshot_origin='MIGRATION_CURRENT' "
        "WHERE status='AWAITING_SUBMISSIONS'"
    )
    # Known keys cannot be bypassed by a missing/wrong client classification.
    op.create_check_constraint(
        "ck_checkin_dimension_class",
        "checkin_dimensions",
        "(dimension_class IS NULL OR dimension_class='INTIMATE') AND "
        "(semantic_key <> 'sexual_connection' OR dimension_class IS NOT DISTINCT FROM 'INTIMATE')",
    )
    op.execute("""
        CREATE FUNCTION checkin_dimension_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.semantic_key IS DISTINCT FROM OLD.semantic_key
             OR NEW.workspace_id IS DISTINCT FROM OLD.workspace_id
             OR NEW.template_version IS DISTINCT FROM OLD.template_version THEN
            RAISE EXCEPTION 'CHECKIN_DIMENSION_IDENTITY_IMMUTABLE';
          END IF;
          IF EXISTS (SELECT 1 FROM relationship_checkins r
                     WHERE r.workspace_id=OLD.workspace_id
                       AND r.checkin_template_version=OLD.template_version) THEN
            RAISE EXCEPTION 'CHECKIN_TEMPLATE_VERSION_FROZEN';
          END IF;
          RETURN NEW;
        END $$
    """)
    op.execute(
        "CREATE TRIGGER checkin_dimension_identity_guard BEFORE UPDATE ON checkin_dimensions "
        "FOR EACH ROW EXECUTE FUNCTION checkin_dimension_identity_guard()"
    )
    op.execute("""
        CREATE FUNCTION checkin_snapshot_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' AND NOT EXISTS (
            SELECT 1 FROM relationship_checkins WHERE id=OLD.checkin_id
          ) THEN RETURN OLD; END IF;
          RAISE EXCEPTION 'CHECKIN_SNAPSHOT_IMMUTABLE';
        END $$
    """)
    op.execute(
        "CREATE TRIGGER checkin_snapshot_guard BEFORE UPDATE OR DELETE ON checkin_round_dimensions "
        "FOR EACH ROW EXECUTE FUNCTION checkin_snapshot_guard()"
    )


def downgrade() -> None:
    db = op.get_bind()
    db.execute(
        sa.text(
            "LOCK TABLE relationship_workspaces, checkin_templates, "
            "checkin_dimensions, relationship_checkins, checkin_responses, "
            "checkin_analyses, checkin_round_dimensions, checkin_idempotency "
            "IN SHARE ROW EXCLUSIVE MODE"
        )
    )
    # Once used, dropping this schema destroys evidence/request identity. Restore a backup instead.
    used = db.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM checkin_round_dimensions) OR "
            "EXISTS (SELECT 1 FROM checkin_idempotency) OR "
            "EXISTS (SELECT 1 FROM checkin_templates WHERE version > 1) OR "
            "EXISTS (SELECT 1 FROM checkin_dimensions WHERE dimension_class IS NOT NULL "
            "AND semantic_key <> 'sexual_connection')"
        )
    ).scalar_one()
    if used:
        raise RuntimeError("CHECKIN_DOWNGRADE_UNSAFE: restore a verified pre-upgrade backup")
    op.execute("DROP TRIGGER checkin_snapshot_guard ON checkin_round_dimensions")
    op.execute("DROP FUNCTION checkin_snapshot_guard()")
    op.execute("DROP TRIGGER checkin_dimension_identity_guard ON checkin_dimensions")
    op.execute("DROP FUNCTION checkin_dimension_identity_guard()")
    op.drop_constraint("ck_checkin_dimension_class", "checkin_dimensions", type_="check")
    op.drop_table("checkin_idempotency")
    op.drop_table("checkin_round_dimensions")
    op.drop_column("relationship_checkins", "snapshot_origin")
    op.drop_index("uq_checkin_templates_active", table_name="checkin_templates")
    op.drop_constraint(
        "uq_checkin_dimensions_workspace_version_key", "checkin_dimensions", type_="unique"
    )
    op.create_unique_constraint(
        "uq_checkin_dimensions_workspace_semantic_key",
        "checkin_dimensions",
        ["workspace_id", "semantic_key"],
    )
    op.drop_column("checkin_dimensions", "dimension_class")
    op.drop_constraint(
        "checkin_responses_dimension_id_fkey", "checkin_responses", type_="foreignkey"
    )
    op.create_foreign_key(
        "checkin_responses_dimension_id_fkey",
        "checkin_responses",
        "checkin_dimensions",
        ["dimension_id"],
        ["id"],
        ondelete="CASCADE",
    )
