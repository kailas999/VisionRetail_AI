"""
Pydantic schemas for FastAPI request/response validation.
Strictly separates API contract from ORM internals.
"""
import uuid
from datetime import datetime, date
from typing import Any, Optional
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────
class EventType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ZONE_ENTER = "ZONE_ENTER"
    ZONE_EXIT = "ZONE_EXIT"
    ZONE_DWELL = "ZONE_DWELL"
    BILLING_QUEUE_JOIN = "BILLING_QUEUE_JOIN"
    BILLING_QUEUE_ABANDON = "BILLING_QUEUE_ABANDON"
    REENTRY = "REENTRY"
    PURCHASE = "PURCHASE"


class AnomalyType(str, Enum):
    QUEUE_SPIKE = "QUEUE_SPIKE"
    CONVERSION_DROP = "CONVERSION_DROP"
    DEAD_ZONE = "DEAD_ZONE"
    TRAFFIC_DROP = "TRAFFIC_DROP"


class Severity(str, Enum):
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ─────────────────────────────────────────────────────────────────────────────
# Event Schemas
# ─────────────────────────────────────────────────────────────────────────────
class EventIngest(BaseModel):
    """Single event payload for ingestion."""

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    store_id: str = Field(..., min_length=1, max_length=64)
    camera_id: str = Field(...)
    visitor_id: str = Field(..., min_length=1, max_length=128)
    event_type: EventType
    timestamp: datetime
    zone_id: Optional[str] = None
    dwell_ms: int = 0
    is_staff: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: Optional[dict[str, Any]] = None

    model_config = {"json_schema_extra": {
        "example": {
            "store_id": "STORE_BLR_002",
            "visitor_id": "VISITOR_abc123",
            "event_type": "ENTRY",
            "timestamp": "2026-05-30T10:00:00+05:30",
            "confidence": 0.92,
        }
    }}


class BatchEventIngest(BaseModel):
    """Batch ingestion payload — up to 1000 events per call."""

    events: list[EventIngest] = Field(..., min_length=1, max_length=500)

    @field_validator("events")
    @classmethod
    def check_unique_ids(cls, events: list[EventIngest]) -> list[EventIngest]:
        ids = [str(e.event_id) for e in events]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate event_id values in batch")
        return events


class EventIngestResponse(BaseModel):
    ingested: int
    duplicates: int
    errors: int
    trace_id: str


# ─────────────────────────────────────────────────────────────────────────────
# Metrics Schemas
# ─────────────────────────────────────────────────────────────────────────────
class HourlyMetricsOut(BaseModel):
    hour_bucket: datetime
    unique_visitors: int
    conversions: int
    avg_dwell_seconds: float
    max_queue_depth: int
    abandonment_count: int
    conversion_rate: float


import datetime as dt

class StoreMetricsOut(BaseModel):
    store_id: str
    date: Optional[dt.date] = None
    unique_visitors: int
    staff_count: int
    conversions: int
    conversion_rate: float
    avg_dwell_seconds: float
    peak_hour: Optional[int] = None
    max_queue_depth: int
    abandonment_count: int
    reentry_count: int
    total_revenue: float
    total_visitors: int = 0
    visitors_after_reid: int = 0
    entry_count: int = 0
    exit_count: int = 0
    zone_engagement_count: int = 0
    billing_queue_count: int = 0
    purchases_count: int = 0
    cross_camera_match_rate: float = 0.0
    hourly_breakdown: list[HourlyMetricsOut] = []


# ─────────────────────────────────────────────────────────────────────────────
# Funnel Schema
# ─────────────────────────────────────────────────────────────────────────────
class FunnelStage(BaseModel):
    stage: str
    count: int
    rate: float              # relative to previous stage


class FunnelOut(BaseModel):
    store_id: str
    date: Optional[dt.date] = None
    stages: list[FunnelStage]


# ─────────────────────────────────────────────────────────────────────────────
# Heatmap Schema
# ─────────────────────────────────────────────────────────────────────────────
class ZoneHeatmapPoint(BaseModel):
    zone_id: str
    zone_name: str
    zone_type: str
    avg_dwell_seconds: float
    visitor_count: int
    zone_enter_count: int = 0
    zone_exit_count: int = 0
    polygon: list[list[float]]       # [[x,y], ...]
    intensity: float                 # 0.0–1.0 normalised


class HeatmapOut(BaseModel):
    store_id: str
    date: Optional[dt.date] = None
    data_source: str
    data_confidence: bool = True   # False if fewer than 20 unique sessions in window
    zones: list[ZoneHeatmapPoint]


# ─────────────────────────────────────────────────────────────────────────────
# Anomaly Schema
# ─────────────────────────────────────────────────────────────────────────────
class AnomalyOut(BaseModel):
    anomaly_id: uuid.UUID
    store_id: str
    detected_at: datetime
    anomaly_type: str
    severity: str
    confidence: float
    metric_value: float
    baseline_value: float
    z_score: float
    affected_zone_id: Optional[str]
    suggested_action: str
    is_resolved: bool


class AnomaliesResponse(BaseModel):
    store_id: str
    active_count: int
    anomalies: list[AnomalyOut]


# ─────────────────────────────────────────────────────────────────────────────
# AI Insight Schema  (GPT-5.2 explanation — not used for detection)
# ─────────────────────────────────────────────────────────────────────────────
class AnomalyInsight(BaseModel):
    """GPT-generated root-cause explanation for a detected anomaly."""

    anomaly_id: str
    store_id: str
    anomaly_type: str
    root_cause: str
    business_impact: str
    recommended_actions: list[str]
    priority_level: str          # LOW | MEDIUM | HIGH | CRITICAL
    fallback: bool = False       # True when rule-based (OpenAI unavailable)
    fallback_reason: Optional[str] = None
    generated_at: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Copilot Schema
# ─────────────────────────────────────────────────────────────────────────────
class AiStoreSummaryResponse(BaseModel):
    store_id: str
    executive_summary: str
    revenue_risk: str
    top_opportunities: str
    recommended_actions: list[str]
    priority_level: str          # LOW | MEDIUM | HIGH | CRITICAL
    fallback: bool = False
    fallback_reason: Optional[str] = None
    generated_at: Optional[str] = None

class CopilotQuery(BaseModel):
    store_id: str
    question: str = Field(..., min_length=5, max_length=500)
    date: Optional[date] = None
    include_context: bool = True

    model_config = {"json_schema_extra": {
        "example": {
            "store_id": "STORE_BLR_002",
            "question": "Why is conversion dropping?",
        }
    }}


class CopilotEvidence(BaseModel):
    metric: str
    value: Any
    context: str


class CopilotResponse(BaseModel):
    store_id: str
    question: str
    observations: list[str]
    evidence: list[CopilotEvidence]
    conclusion: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    insufficient_data: bool = False
    trace_id: str


# ─────────────────────────────────────────────────────────────────────────────
# Event Stream Schema
# ─────────────────────────────────────────────────────────────────────────────
class EntranceStats(BaseModel):
    entry_count: int
    exit_count: int
    reentry_count: int
    current_occupancy: int

class ZoneStats(BaseModel):
    zone_enter_count: int
    zone_exit_count: int
    zone_dwell_count: int
    avg_dwell_seconds: float

class BillingStats(BaseModel):
    queue_join_count: int
    queue_abandon_count: int
    purchase_count: int
    queue_abandon_rate: float
    billing_conversion_rate: float = 0.0

class ReidStats(BaseModel):
    cross_camera_matches: int
    match_rate: float
    fragmented_visitors: int
    avg_confidence: float

class EventStreamResponse(BaseModel):
    entrance: EntranceStats
    zone: ZoneStats
    billing: BillingStats
    reid: ReidStats


# ─────────────────────────────────────────────────────────────────────────────
# Health Schema
# ─────────────────────────────────────────────────────────────────────────────
class StoreHealthStat(BaseModel):
    store_id: str
    last_event_at: Optional[datetime]   # UTC timestamp of most recent event
    lag_seconds: Optional[float]        # seconds since last event (None if no events)
    stale_feed: bool                    # True if lag > 10 minutes


class HealthOut(BaseModel):
    status: str
    database: str
    version: str = "1.0.0"
    environment: str
    store_stats: list[StoreHealthStat] = []  # per-store feed freshness
