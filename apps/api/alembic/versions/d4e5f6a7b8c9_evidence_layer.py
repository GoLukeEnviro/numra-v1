"""evidence layer: life tracking + deterministic correlation analysis (PR-V2-11)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-09-08 02:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, table

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: Ad-hoc-Tabelle nur fuer den Seed-Insert unten (Alembic-Cookbook-Muster) -- die
#: echte Tabellendefinition steht in models/tables.py::EvidencePolicy.
_evidence_policies = table(
    "evidence_policies",
    column("id", postgresql.UUID(as_uuid=True)),
    column("version", sa.Integer),
    column("active", sa.Boolean),
    column("minimum_total_sample_count", sa.Integer),
    column("minimum_sample_count_per_bucket", sa.Integer),
    column("minimum_observation_window_days", sa.Integer),
    column("missing_data_handling", sa.String),
    column("outlier_policy", sa.String),
    column("multiple_comparison_protection", sa.String),
    column("effect_size_threshold", sa.Numeric),
    column("confidence_category_thresholds", postgresql.JSONB),
    column("rationale", sa.Text),
)

#: specs/v2/evidence-policy.md: "Every threshold must have a documented rationale in
#: the policy's changelog -- no 'magic number' without justification." Dieser Text
#: IST dieser Changelog-Eintrag und wird mit der Zeile gespeichert, nicht nur hier
#: als Kommentar -- eine spaetere Version 2 muss ihre eigene Begruendung mitbringen.
_POLICY_V1_RATIONALE = (
    "Version 1, Erstfassung zum Start des Evidence Layer.\n"
    "\n"
    "minimum_total_sample_count = 30: Unterhalb von rund 30 Messtagen ist der "
    "persoenliche Baseline-Mittelwert selbst noch so instabil, dass jede Abweichung "
    "eines einzelnen Buckets ueberwiegend Rauschen der Baseline waere. 30 ist die "
    "konventionelle Untergrenze, ab der eine Mittelwertschaetzung als brauchbar gilt.\n"
    "\n"
    "minimum_sample_count_per_bucket = 5: Ein Personal-Day-Wert wiederholt sich im "
    "Schnitt etwa jeden neunten Tag. 5 Treffer verlangen also faktisch rund 45 Tage "
    "Beobachtung und verhindern, dass zwei oder drei zufaellige Ausreissertage einen "
    "Bucket-Mittelwert vollstaendig bestimmen.\n"
    "\n"
    "minimum_observation_window_days = 45: Passt zur Bucket-Mindestzahl (siehe oben) "
    "und stellt sicher, dass sich der Zeitraum ueber mehr als einen Personal Month "
    "erstreckt -- 30 dicht getrackte Tage innerhalb eines einzigen Monats wuerden "
    "sonst als vollwertige Historie durchgehen.\n"
    "\n"
    "missing_data_handling = EXCLUDE: Ein Tag ohne Messwert wird verworfen und zaehlt "
    "auch nicht zum Beobachtungszeitraum. Interpoliert wird nie -- ein erfundener "
    "Wert wuerde die Stichprobengroesse aufblaehen, die der Nutzer im Statement "
    "angezeigt bekommt.\n"
    "\n"
    "outlier_policy = WINSORIZE_P95: Einzelne Extremtage (etwa Krankheit) werden auf "
    "das 5./95. Perzentil gekappt statt entfernt. Kappen erhaelt die "
    "Stichprobengroesse; Entfernen wuerde den Tag doppelt bestrafen, indem es "
    "zusaetzlich die berichtete Evidenzbasis senkt.\n"
    "\n"
    "multiple_comparison_protection = NONE: Version 1 beantwortet jeweils genau eine "
    "vom Nutzer explizit gestellte Frage (eine Metrik, ein Bucket-Wert). Es gibt in "
    "diesem Release keinen Pfad, der automatisch ueber alle Buckets scannt, also auch "
    "keine Familie von Vergleichen, gegen die zu korrigieren waere. Sobald ein "
    "solcher Scan eingefuehrt wird, MUSS eine neue Policy-Version auf BONFERRONI "
    "gehen.\n"
    "\n"
    "effect_size_threshold = 0.500: Standardisierte Mittelwertdifferenz (Cohen-d-Form) "
    "gegen die persoenliche Baseline-Streuung. 0.5 ist Cohens konventionelle Grenze "
    "fuer einen mittleren Effekt; darunter wird bewusst NO_RELIABLE_PATTERN gemeldet, "
    "statt einen im Alltag nicht spuerbaren Unterschied zu behaupten.\n"
    "\n"
    "confidence_category_thresholds = {LOW: 0.5, MEDIUM: 0.65, HIGH: 0.8}: Setzt bei "
    "effect_size_threshold auf, damit unterhalb der Ausspielgrenze gar keine Kategorie "
    "vergeben wird. 0.8 ist Cohens Grenze fuer einen grossen Effekt; 0.65 liegt "
    "mittig dazwischen und trennt LOW von MEDIUM."
)


def upgrade() -> None:
    """Rein additiv -- fuenf neue Tabellen, kein Backfill. Der Seed der
    `EvidencePolicy`-Version 1 ist Teil des Schemas, nicht optionale Testdaten:
    ohne aktive Policy verweigert services/evidence_service.py jede Berechnung
    (EVIDENCE_POLICY_NOT_FOUND), statt still eine Schwelle zu erfinden."""
    op.create_table(
        "life_tracking_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entry_date", sa.Date(), nullable=False),
        # SET NULL, nicht CASCADE: `calculation_id` ist reine Provenienz. Ein
        # geloeschter Calculation-Snapshot darf niemals den getrackten Tag mitreissen
        # (gleiches Muster wie `ChatMessage.author_user_id`).
        sa.Column(
            "calculation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("calculations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("mood", sa.SmallInteger(), nullable=True),
        sa.Column("energy", sa.SmallInteger(), nullable=True),
        sa.Column("sleep", sa.SmallInteger(), nullable=True),
        sa.Column("stress", sa.SmallInteger(), nullable=True),
        sa.Column("focus", sa.SmallInteger(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("person_id", "entry_date", name="uq_life_tracking_entries_person_date"),
        sa.CheckConstraint(
            "mood IS NULL OR mood BETWEEN 1 AND 10", name="ck_life_tracking_entries_mood_range"
        ),
        sa.CheckConstraint(
            "energy IS NULL OR energy BETWEEN 1 AND 10",
            name="ck_life_tracking_entries_energy_range",
        ),
        sa.CheckConstraint(
            "sleep IS NULL OR sleep BETWEEN 1 AND 10", name="ck_life_tracking_entries_sleep_range"
        ),
        sa.CheckConstraint(
            "stress IS NULL OR stress BETWEEN 1 AND 10",
            name="ck_life_tracking_entries_stress_range",
        ),
        sa.CheckConstraint(
            "focus IS NULL OR focus BETWEEN 1 AND 10", name="ck_life_tracking_entries_focus_range"
        ),
    )
    op.create_index("ix_life_tracking_entries_user_id", "life_tracking_entries", ["user_id"])
    op.create_index("ix_life_tracking_entries_person_id", "life_tracking_entries", ["person_id"])

    op.create_table(
        "custom_metric_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_key", sa.String(60), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("scale_min", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("scale_max", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "person_id", "metric_key", name="uq_custom_metric_definitions_person_metric_key"
        ),
    )
    op.create_index(
        "ix_custom_metric_definitions_person_id", "custom_metric_definitions", ["person_id"]
    )

    op.create_table(
        "life_tracking_metric_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("life_tracking_entries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric_key", sa.String(60), nullable=False),
        sa.Column("value", sa.SmallInteger(), nullable=False),
        sa.UniqueConstraint(
            "entry_id", "metric_key", name="uq_life_tracking_metric_values_entry_metric_key"
        ),
    )
    op.create_index(
        "ix_life_tracking_metric_values_entry_id", "life_tracking_metric_values", ["entry_id"]
    )

    op.create_table(
        "evidence_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("minimum_total_sample_count", sa.Integer(), nullable=False),
        sa.Column("minimum_sample_count_per_bucket", sa.Integer(), nullable=False),
        sa.Column("minimum_observation_window_days", sa.Integer(), nullable=False),
        sa.Column("missing_data_handling", sa.String(30), nullable=False),
        sa.Column("outlier_policy", sa.String(30), nullable=False),
        sa.Column("multiple_comparison_protection", sa.String(30), nullable=False),
        sa.Column("effect_size_threshold", sa.Numeric(4, 3), nullable=False),
        sa.Column("confidence_category_thresholds", postgresql.JSONB(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    # Genau eine aktive Version, DB-erzwungen -- gleiches Muster wie
    # `uq_people_user_id_self_mode`. Ohne diesen Index koennte ein fehlerhafter
    # Versionswechsel zwei aktive Policies hinterlassen und
    # repositories/evidence.py::get_active_evidence_policy wuerde nicht-deterministisch
    # eine davon liefern.
    op.create_index(
        "uq_evidence_policies_one_active",
        "evidence_policies",
        ["active"],
        unique=True,
        postgresql_where=sa.text("active = true"),
    )

    op.create_table(
        "pattern_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "person_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Bewusst KEIN Fremdschluessel auf `evidence_policies.version`: ein
        # Snapshot-Integer, damit ein spaeterer Versionswechsel die Historie nicht
        # umschreibt (gleiches Muster wie `RelationshipAnalysis.calculation_version`).
        sa.Column("evidence_policy_version", sa.Integer(), nullable=False),
        sa.Column("metric_key", sa.String(60), nullable=False),
        sa.Column("correlation_target", sa.String(30), nullable=False),
        sa.Column("correlation_target_value", sa.Integer(), nullable=False),
        sa.Column("result_json", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_pattern_analyses_person_id", "pattern_analyses", ["person_id"])
    op.create_index("ix_pattern_analyses_user_id", "pattern_analyses", ["user_id"])

    op.bulk_insert(
        _evidence_policies,
        [
            {
                "id": "00000000-0000-0000-0000-0000000000e1",
                "version": 1,
                "active": True,
                "minimum_total_sample_count": 30,
                "minimum_sample_count_per_bucket": 5,
                "minimum_observation_window_days": 45,
                "missing_data_handling": "EXCLUDE",
                "outlier_policy": "WINSORIZE_P95",
                "multiple_comparison_protection": "NONE",
                "effect_size_threshold": 0.500,
                "confidence_category_thresholds": {"LOW": 0.5, "MEDIUM": 0.65, "HIGH": 0.8},
                "rationale": _POLICY_V1_RATIONALE,
            }
        ],
    )


def downgrade() -> None:
    """Symmetrisch. Die Seed-Zeile verschwindet mit `evidence_policies` -- ein
    separates DELETE waere ueberfluessig."""
    op.drop_index("ix_pattern_analyses_user_id", table_name="pattern_analyses")
    op.drop_index("ix_pattern_analyses_person_id", table_name="pattern_analyses")
    op.drop_table("pattern_analyses")

    op.drop_index("uq_evidence_policies_one_active", table_name="evidence_policies")
    op.drop_table("evidence_policies")

    op.drop_index(
        "ix_life_tracking_metric_values_entry_id", table_name="life_tracking_metric_values"
    )
    op.drop_table("life_tracking_metric_values")

    op.drop_index("ix_custom_metric_definitions_person_id", table_name="custom_metric_definitions")
    op.drop_table("custom_metric_definitions")

    op.drop_index("ix_life_tracking_entries_person_id", table_name="life_tracking_entries")
    op.drop_index("ix_life_tracking_entries_user_id", table_name="life_tracking_entries")
    op.drop_table("life_tracking_entries")
