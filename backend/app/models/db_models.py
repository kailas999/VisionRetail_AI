"""
SQLAlchemy ORM models for VisionRetail AI.

Design decisions:
- UUID PKs everywhere for distributed-safe event IDs (no sequence collision).
- Pre-aggregated hourly_metrics / daily_metrics avoid full table scans on API.
- JSONB columns for flexible metadata (zone polygon, event metadata).
- Composite indexes on (store_id, timestamp) cover all time-range queries.
"""
import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.types import JSON, Uuid as _Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Dialect-agnostic aliases: on PostgreSQL these render as JSONB/UUID natively;
# on SQLite (tests) they render as TEXT/CHAR(36) — no custom compiler needed.
# native_uuid=False → store as CHAR(36) string; avoids bytes .hex issue on SQLite.
JSONB = JSON


def Uuid(**kw):  # noqa: N802 – match original capitalisation used throughout file
    """Factory returning a cross-database UUID column type (stored as CHAR-36 string)."""
    kw.setdefault("native_uuid", False)
    return _Uuid(**kw)


from app.database import Base


# ─────────────────────────────────────────────────────────────────────────────
# Stores
# ─────────────────────────────────────────────────────────────────────────────
class Store(Base):
    __tablename__ = "stores"

    store_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    zones: Mapped[list["Zone"]] = relationship("Zone", back_populates="store")
    sessions: Mapped[list["VisitorSession"]] = relationship(
        "VisitorSession", back_populates="store"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Zones
# ─────────────────────────────────────────────────────────────────────────────
class Zone(Base):
    __tablename__ = "zones"

    zone_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    store_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    zone_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # ENTRY, EXIT, DISPLAY, BILLING, AISLE
    polygon_json: Mapped[dict] = mapped_column(JSONB, nullable=False)  # [[x,y], ...]
    priority: Mapped[int] = mapped_column(Integer, default=0)  # higher = checked first
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    store: Mapped["Store"] = relationship("Store", back_populates="zones")

    __table_args__ = (Index("ix_zones_store_id", "store_id"),)


# ─────────────────────────────────────────────────────────────────────────────
# Visitor Sessions
# ─────────────────────────────────────────────────────────────────────────────
class VisitorSession(Base):
    __tablename__ = "visitor_sessions"

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False
    )
    visitor_id: Mapped[str] = mapped_column(
        String(128), nullable=False
    )  # Re-ID stable ID
    track_ids: Mapped[list] = mapped_column(
        JSONB, default=list
    )  # ByteTrack IDs across cameras
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dwell_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_converted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    is_reentry: Mapped[bool] = mapped_column(Boolean, default=False)
    zones_visited: Mapped[list] = mapped_column(JSONB, default=list)  # [zone_id, ...]
    sequence_number: Mapped[int] = mapped_column(Integer, default=1)
    camera_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    store: Mapped["Store"] = relationship("Store", back_populates="sessions")
    events: Mapped[list["Event"]] = relationship("Event", back_populates="session")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="session"
    )

    __table_args__ = (
        Index("ix_sessions_store_entry", "store_id", "entry_time"),
        Index("ix_sessions_visitor", "visitor_id"),
        Index("ix_sessions_store_converted", "store_id", "is_converted"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Events
# ─────────────────────────────────────────────────────────────────────────────
class Event(Base):
    __tablename__ = "events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(),
        ForeignKey("visitor_sessions.session_id", ondelete="SET NULL"),
        nullable=True,
    )
    visitor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # ENTRY, EXIT, ZONE_ENTER, etc.
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    zone_id: Mapped[Optional[str]] = mapped_column(
        String(64), ForeignKey("zones.zone_id", ondelete="SET NULL"), nullable=True
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    camera_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    bbox_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    sequence_number: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped[Optional["VisitorSession"]] = relationship(
        "VisitorSession", back_populates="events"
    )

    __table_args__ = (
        Index("ix_events_store_ts", "store_id", "timestamp"),
        Index("ix_events_visitor", "visitor_id"),
        Index("ix_events_type", "event_type"),
        Index("ix_events_session", "session_id"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Transactions (POS)
# ─────────────────────────────────────────────────────────────────────────────
class Transaction(Base):
    __tablename__ = "transactions"

    tx_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(),
        ForeignKey("visitor_sessions.session_id", ondelete="SET NULL"),
        nullable=True,
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    pos_terminal_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped[Optional["VisitorSession"]] = relationship(
        "VisitorSession", back_populates="transactions"
    )

    __table_args__ = (Index("ix_transactions_store_ts", "store_id", "timestamp"),)


# ─────────────────────────────────────────────────────────────────────────────
# Pre-aggregated Hourly Metrics
# ─────────────────────────────────────────────────────────────────────────────
class HourlyMetrics(Base):
    __tablename__ = "hourly_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False
    )
    hour_bucket: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )  # truncated to hour
    unique_visitors: Mapped[int] = mapped_column(Integer, default=0)
    staff_count: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    avg_dwell_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    max_queue_depth: Mapped[int] = mapped_column(Integer, default=0)
    abandonment_count: Mapped[int] = mapped_column(Integer, default=0)
    reentry_count: Mapped[int] = mapped_column(Integer, default=0)
    zone_dwell_json: Mapped[dict] = mapped_column(
        JSONB, default=dict
    )  # {zone_id: avg_seconds}
    total_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("store_id", "hour_bucket", name="uq_hourly_store_hour"),
        Index("ix_hourly_store_bucket", "store_id", "hour_bucket"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Pre-aggregated Daily Metrics
# ─────────────────────────────────────────────────────────────────────────────
class DailyMetrics(Base):
    __tablename__ = "daily_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    store_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False
    )
    date_bucket: Mapped[date] = mapped_column(Date, nullable=False)
    unique_visitors: Mapped[int] = mapped_column(Integer, default=0)
    staff_count: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_dwell_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    peak_hour: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_queue_depth: Mapped[int] = mapped_column(Integer, default=0)
    abandonment_count: Mapped[int] = mapped_column(Integer, default=0)
    reentry_count: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue: Mapped[float] = mapped_column(Float, default=0.0)
    zone_dwell_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("store_id", "date_bucket", name="uq_daily_store_date"),
        Index("ix_daily_store_date", "store_id", "date_bucket"),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Anomalies
# ─────────────────────────────────────────────────────────────────────────────
class Anomaly(Base):
    __tablename__ = "anomalies"

    anomaly_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), primary_key=True, default=uuid.uuid4
    )
    store_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("stores.store_id", ondelete="CASCADE"), nullable=False
    )
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    anomaly_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # QUEUE_SPIKE, CONVERSION_DROP, DEAD_ZONE, TRAFFIC_DROP
    severity: Mapped[str] = mapped_column(String(16), nullable=False)  # MEDIUM/HIGH/CRITICAL
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_value: Mapped[float] = mapped_column(Float, nullable=False)
    z_score: Mapped[float] = mapped_column(Float, nullable=False)
    affected_zone_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    recommended_action: Mapped[str] = mapped_column(Text, nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_anomalies_store_detected", "store_id", "detected_at"),
        Index("ix_anomalies_unresolved", "store_id", "is_resolved"),
    )
