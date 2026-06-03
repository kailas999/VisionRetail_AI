"""Initial schema — creates all tables with indexes and constraints."""
import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── stores ────────────────────────────────────────────────────────────────
    op.create_table(
        "stores",
        sa.Column("store_id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Kolkata"),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # ── zones ─────────────────────────────────────────────────────────────────
    op.create_table(
        "zones",
        sa.Column("zone_id", sa.String(64), primary_key=True),
        sa.Column(
            "store_id",
            sa.String(64),
            sa.ForeignKey("stores.store_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("zone_type", sa.String(64), nullable=False),
        sa.Column("polygon_json", postgresql.JSONB, nullable=False),
        sa.Column("priority", sa.Integer, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_zones_store_id", "zones", ["store_id"])

    # ── visitor_sessions ──────────────────────────────────────────────────────
    op.create_table(
        "visitor_sessions",
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "store_id",
            sa.String(64),
            sa.ForeignKey("stores.store_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("visitor_id", sa.String(128), nullable=False),
        sa.Column("track_ids", postgresql.JSONB, server_default="[]"),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dwell_seconds", sa.Float, nullable=True),
        sa.Column("is_converted", sa.Boolean, server_default="false"),
        sa.Column("is_staff", sa.Boolean, server_default="false"),
        sa.Column("is_reentry", sa.Boolean, server_default="false"),
        sa.Column("zones_visited", postgresql.JSONB, server_default="[]"),
        sa.Column("sequence_number", sa.Integer, server_default="1"),
        sa.Column("camera_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_sessions_store_entry", "visitor_sessions", ["store_id", "entry_time"])
    op.create_index("ix_sessions_visitor", "visitor_sessions", ["visitor_id"])
    op.create_index("ix_sessions_store_converted", "visitor_sessions", ["store_id", "is_converted"])

    # ── events ────────────────────────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column(
            "event_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "store_id",
            sa.String(64),
            sa.ForeignKey("stores.store_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("visitor_sessions.session_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("visitor_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "zone_id",
            sa.String(64),
            sa.ForeignKey("zones.zone_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("confidence", sa.Float, server_default="1.0"),
        sa.Column("is_staff", sa.Boolean, server_default="false"),
        sa.Column("camera_id", sa.String(64), nullable=True),
        sa.Column("bbox_json", postgresql.JSONB, nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column("sequence_number", sa.Integer, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_events_store_ts", "events", ["store_id", "timestamp"])
    op.create_index("ix_events_visitor", "events", ["visitor_id"])
    op.create_index("ix_events_type", "events", ["event_type"])
    op.create_index("ix_events_session", "events", ["session_id"])

    # ── transactions ──────────────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column(
            "tx_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "store_id",
            sa.String(64),
            sa.ForeignKey("stores.store_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("visitor_sessions.session_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pos_terminal_id", sa.String(64), nullable=True),
        sa.Column("raw_json", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_transactions_store_ts", "transactions", ["store_id", "timestamp"])

    # ── hourly_metrics ────────────────────────────────────────────────────────
    op.create_table(
        "hourly_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "store_id",
            sa.String(64),
            sa.ForeignKey("stores.store_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hour_bucket", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unique_visitors", sa.Integer, server_default="0"),
        sa.Column("staff_count", sa.Integer, server_default="0"),
        sa.Column("conversions", sa.Integer, server_default="0"),
        sa.Column("avg_dwell_seconds", sa.Float, server_default="0"),
        sa.Column("max_queue_depth", sa.Integer, server_default="0"),
        sa.Column("abandonment_count", sa.Integer, server_default="0"),
        sa.Column("reentry_count", sa.Integer, server_default="0"),
        sa.Column("zone_dwell_json", postgresql.JSONB, server_default="{}"),
        sa.Column("total_revenue", sa.Float, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("store_id", "hour_bucket", name="uq_hourly_store_hour"),
    )
    op.create_index("ix_hourly_store_bucket", "hourly_metrics", ["store_id", "hour_bucket"])

    # ── daily_metrics ─────────────────────────────────────────────────────────
    op.create_table(
        "daily_metrics",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "store_id",
            sa.String(64),
            sa.ForeignKey("stores.store_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date_bucket", sa.Date, nullable=False),
        sa.Column("unique_visitors", sa.Integer, server_default="0"),
        sa.Column("staff_count", sa.Integer, server_default="0"),
        sa.Column("conversions", sa.Integer, server_default="0"),
        sa.Column("conversion_rate", sa.Float, server_default="0"),
        sa.Column("avg_dwell_seconds", sa.Float, server_default="0"),
        sa.Column("peak_hour", sa.Integer, nullable=True),
        sa.Column("max_queue_depth", sa.Integer, server_default="0"),
        sa.Column("abandonment_count", sa.Integer, server_default="0"),
        sa.Column("reentry_count", sa.Integer, server_default="0"),
        sa.Column("total_revenue", sa.Float, server_default="0"),
        sa.Column("zone_dwell_json", postgresql.JSONB, server_default="{}"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
        sa.UniqueConstraint("store_id", "date_bucket", name="uq_daily_store_date"),
    )
    op.create_index("ix_daily_store_date", "daily_metrics", ["store_id", "date_bucket"])

    # ── anomalies ─────────────────────────────────────────────────────────────
    op.create_table(
        "anomalies",
        sa.Column(
            "anomaly_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "store_id",
            sa.String(64),
            sa.ForeignKey("stores.store_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("anomaly_type", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("metric_value", sa.Float, nullable=False),
        sa.Column("baseline_value", sa.Float, nullable=False),
        sa.Column("z_score", sa.Float, nullable=False),
        sa.Column("affected_zone_id", sa.String(64), nullable=True),
        sa.Column("recommended_action", sa.Text, nullable=False),
        sa.Column("is_resolved", sa.Boolean, server_default="false"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_anomalies_store_detected", "anomalies", ["store_id", "detected_at"])
    op.create_index("ix_anomalies_unresolved", "anomalies", ["store_id", "is_resolved"])


def downgrade() -> None:
    op.drop_table("anomalies")
    op.drop_table("daily_metrics")
    op.drop_table("hourly_metrics")
    op.drop_table("transactions")
    op.drop_table("events")
    op.drop_table("visitor_sessions")
    op.drop_table("zones")
    op.drop_table("stores")
