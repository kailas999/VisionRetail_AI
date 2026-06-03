"""FastAPI metrics and funnel routers.

All analytics are derived from a single visitor-journey CTE that enforces
the retail hierarchy by boolean multiplication:

    reached_purchase = has_entry × has_engagement × has_billing × has_purchase

This makes Purchase <= Billing <= Engagement <= Entry mathematically unbreakable.

Fixes applied:
  CF-01 – conversion_rate uses DISTINCT purchaser visitor_ids (not event count)
  CF-05 – /metrics shares the same journey CTE as /funnel
  CF-06 – hierarchy check applied to both endpoints
  CF-07 – billing_queue_count = DISTINCT visitors (not BILLING_QUEUE_JOIN events)
  CF-08 – open sessions included in avg_dwell via COALESCE
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.schemas import StoreMetricsOut, HourlyMetricsOut, FunnelOut, FunnelStage, AiStoreSummaryResponse
from app.services.insight_service import generate_store_summary
from app.utils.logging import get_logger

router = APIRouter(prefix="/stores", tags=["Metrics"])
logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Shared visitor-journey funnel CTE
# Called by BOTH /funnel and /metrics so numbers are always identical.
# ─────────────────────────────────────────────────────────────────────────────

async def _compute_journey_funnel(
    db: AsyncSession, store_id: str, query_date: date
) -> dict:
    """
    Execute the unified visitor-journey CTE.

    Returns a dict with all stage counts. Every count is DISTINCT visitor_ids.
    Hierarchy is guaranteed by the CTE multiplication — no runtime enforcement needed,
    but a warning is still logged if upstream data somehow violates it.

    Fixes: CF-01, CF-05, CF-06, CF-07
    """
    conn = await db.connection()
    is_sqlite = conn.dialect.name == "sqlite"

    staff_filter  = "is_staff = 0"                          if is_sqlite else "is_staff = false"
    date_filter   = "DATE(timestamp)"                        if is_sqlite else "DATE(timestamp AT TIME ZONE 'UTC')"

    funnel_sql = text(f"""
        WITH visitor_stages AS (
            SELECT
                visitor_id,
                MAX(CASE WHEN event_type = 'ENTRY'              THEN 1 ELSE 0 END) AS has_entry,
                MAX(CASE WHEN event_type IN ('ZONE_ENTER','ZONE_DWELL')
                                                                THEN 1 ELSE 0 END) AS has_engagement,
                MAX(CASE WHEN event_type = 'BILLING_QUEUE_JOIN' THEN 1 ELSE 0 END) AS has_billing,
                MAX(CASE WHEN event_type = 'PURCHASE'           THEN 1 ELSE 0 END) AS has_purchase,
                MAX(CASE WHEN event_type = 'EXIT'               THEN 1 ELSE 0 END) AS has_exit,
                MAX(CASE WHEN event_type = 'REENTRY'            THEN 1 ELSE 0 END) AS has_reentry,
                COUNT(DISTINCT camera_id)                                           AS cam_count
            FROM events
            WHERE store_id      = :store_id
              AND {staff_filter}
              AND {date_filter}  = :date_bucket
            GROUP BY visitor_id
        ),
        visitor_journeys AS (
            SELECT
                visitor_id,
                has_entry,
                has_exit,
                has_reentry,
                cam_count,
                (has_entry * has_engagement)                               AS reached_engagement,
                (has_entry * has_engagement * has_billing)                 AS reached_billing,
                (has_entry * has_engagement * has_billing * has_purchase)  AS reached_purchase
            FROM visitor_stages
        )
        SELECT
            COUNT(DISTINCT visitor_id)                                          AS unique_visitors,
            COALESCE(SUM(has_entry),           0)                               AS entries,
            COALESCE(SUM(reached_engagement),  0)                               AS zone_engagements,
            COALESCE(SUM(reached_billing),     0)                               AS billing_zone_reached,
            COALESCE(SUM(reached_purchase),    0)                               AS converted,
            COALESCE(SUM(has_exit),            0)                               AS exit_count,
            COALESCE(SUM(has_reentry),         0)                               AS reentry_count,
            CAST(
                COUNT(DISTINCT CASE WHEN cam_count > 1 THEN visitor_id END) AS REAL
            ) / NULLIF(COUNT(DISTINCT visitor_id), 0)                           AS cross_camera_match_rate
        FROM visitor_journeys
    """)

    result = await db.execute(funnel_sql, {"store_id": store_id, "date_bucket": query_date})
    row = result.fetchone()

    if not row:
        return _empty_journey()

    entries   = int(row.entries           or 0)
    zone_eng  = int(row.zone_engagements  or 0)
    billing   = int(row.billing_zone_reached or 0)
    converted = int(row.converted         or 0)
    uv        = int(row.unique_visitors   or 0)

    if not (converted <= billing <= zone_eng <= entries):
        logger.warning(
            "Journey funnel hierarchy violated (upstream data integrity issue)",
            extra={
                "store_id": store_id, "date": str(query_date),
                "entries": entries, "zone_eng": zone_eng,
                "billing": billing, "converted": converted,
            },
        )

    return {
        "unique_visitors":         uv,
        "visitors_after_reid":     uv,
        "total_visitors":          uv,
        "entry_count":             entries,
        "zone_engagement_count":   zone_eng,
        "billing_queue_count":     billing,
        "purchases_count":         converted,
        "exit_count":              int(row.exit_count  or 0),
        "reentry_count":           int(row.reentry_count or 0),
        "cross_camera_match_rate": float(row.cross_camera_match_rate or 0.0),
    }


def _empty_journey() -> dict:
    return {
        "unique_visitors": 0, "visitors_after_reid": 0, "total_visitors": 0,
        "entry_count": 0, "zone_engagement_count": 0, "billing_queue_count": 0,
        "purchases_count": 0, "exit_count": 0, "reentry_count": 0,
        "cross_camera_match_rate": 0.0,
    }


def _enforce_hierarchy(store_id: str, entries: int, zone_eng: int,
                        billing: int, converted: int) -> None:
    """Raise HTTP 500 if the funnel hierarchy is violated."""
    if not (converted <= billing <= zone_eng <= entries):
        logger.error(
            "Funnel hierarchy violation",
            extra={
                "store_id": store_id, "entries": entries,
                "zone_eng": zone_eng, "billing": billing, "converted": converted,
            },
        )
        raise HTTPException(
            status_code=500,
            detail=(
                f"Funnel validation failed: "
                f"Purchase({converted}) <= Billing({billing}) <= "
                f"Engagement({zone_eng}) <= Entry({entries}) is violated."
            ),
        )


# ─────────────────────────────────────────────────────────────────────────────
# GET /stores/{store_id}/metrics
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{store_id}/metrics",
    response_model=StoreMetricsOut,
    summary="Get store metrics (visitor-journey based)",
)
async def get_metrics(
    store_id: str,
    date_filter: Optional[date] = Query(default=None, alias="date"),
    db: AsyncSession = Depends(get_db),
) -> StoreMetricsOut:
    """
    Returns daily metrics for a store.

    Journey metrics (visitors, funnel stages, conversion rate) are ALWAYS
    computed live from the events table via the shared visitor-journey CTE.
    Supplementary data (avg_dwell, peak_hour, revenue, max_queue) is read
    from pre-aggregated daily_metrics when available.

    conversion_rate = distinct_purchasers / distinct_entrants — CANNOT exceed 1.0.
    """
    query_date = date_filter or date.today()

    # 1. Journey funnel — single source of truth for all funnel counts
    j = await _compute_journey_funnel(db, store_id, query_date)

    entries   = j["entry_count"]
    zone_eng  = j["zone_engagement_count"]
    billing   = j["billing_queue_count"]
    converted = j["purchases_count"]

    # CF-06: enforce hierarchy on /metrics too
    _enforce_hierarchy(store_id, entries, zone_eng, billing, converted)

    # CF-01: denominator = entrants, capped at 1.0
    conv_rate = round(converted / max(1, entries), 4) if entries > 0 else 0.0
    conv_rate = min(conv_rate, 1.0)

    # 2. Supplementary pre-aggregated data
    row = None
    result = await db.execute(
        text("""
            SELECT staff_count, avg_dwell_seconds, peak_hour,
                   max_queue_depth, total_revenue
            FROM daily_metrics
            WHERE store_id = :store_id AND date_bucket = :date_bucket
        """),
        {"store_id": store_id, "date_bucket": query_date},
    )
    row = result.fetchone()

    staff_count   = int(row.staff_count       or 0)   if row else 0
    avg_dwell     = float(row.avg_dwell_seconds or 0.0) if row else 0.0
    peak_hour     = row.peak_hour                       if row else None
    max_queue     = int(row.max_queue_depth   or 0)   if row else 0
    total_revenue = float(row.total_revenue   or 0.0) if row else 0.0

    # If no pre-aggregated data, fall back to live session query
    if not row:
        live = await _live_supplementary(db, store_id, query_date)
        staff_count   = live["staff_count"]
        avg_dwell     = live["avg_dwell"]
        total_revenue = live["total_revenue"]

    # 3. Hourly breakdown
    conn = await db.connection()
    is_sqlite = conn.dialect.name == "sqlite"
    if is_sqlite:
        hourly_q = text("""
            SELECT hour_bucket, unique_visitors, conversions,
                   avg_dwell_seconds, max_queue_depth, abandonment_count
            FROM hourly_metrics
            WHERE store_id = :store_id AND DATE(hour_bucket) = :date_bucket
            ORDER BY hour_bucket
        """)
    else:
        hourly_q = text("""
            SELECT hour_bucket, unique_visitors, conversions,
                   avg_dwell_seconds, max_queue_depth, abandonment_count
            FROM hourly_metrics
            WHERE store_id = :store_id
              AND DATE(hour_bucket AT TIME ZONE 'UTC') = :date_bucket
            ORDER BY hour_bucket
        """)
    hourly_res  = await db.execute(hourly_q, {"store_id": store_id, "date_bucket": query_date})
    hourly_rows = hourly_res.fetchall()
    hourly = [
        HourlyMetricsOut(
            hour_bucket=r.hour_bucket,
            unique_visitors=r.unique_visitors,
            conversions=r.conversions,
            avg_dwell_seconds=r.avg_dwell_seconds,
            max_queue_depth=r.max_queue_depth,
            abandonment_count=r.abandonment_count,
            conversion_rate=round(r.conversions / max(1, r.unique_visitors), 4),
        )
        for r in hourly_rows
    ]

    # 4. Abandonment count — DISTINCT visitors (CF-07 pattern)
    if is_sqlite:
        ab_q = text("""
            SELECT COUNT(DISTINCT visitor_id) AS cnt
            FROM events
            WHERE store_id = :store_id AND is_staff = 0
              AND event_type = 'BILLING_QUEUE_ABANDON'
              AND DATE(timestamp) = :date_bucket
        """)
    else:
        ab_q = text("""
            SELECT COUNT(DISTINCT visitor_id) AS cnt
            FROM events
            WHERE store_id = :store_id AND is_staff = false
              AND event_type = 'BILLING_QUEUE_ABANDON'
              AND DATE(timestamp AT TIME ZONE 'UTC') = :date_bucket
        """)
    ab_res = await db.execute(ab_q, {"store_id": store_id, "date_bucket": query_date})
    ab_row = ab_res.fetchone()
    abandonment_count = int(ab_row.cnt or 0) if ab_row else 0

    return StoreMetricsOut(
        store_id=store_id,
        date=query_date,
        unique_visitors=j["unique_visitors"],
        staff_count=staff_count,
        conversions=converted,
        conversion_rate=conv_rate,
        avg_dwell_seconds=avg_dwell,
        peak_hour=peak_hour,
        max_queue_depth=max_queue,
        abandonment_count=abandonment_count,
        reentry_count=j["reentry_count"],
        total_revenue=total_revenue,
        total_visitors=j["total_visitors"],
        visitors_after_reid=j["visitors_after_reid"],
        entry_count=entries,
        exit_count=j["exit_count"],
        zone_engagement_count=zone_eng,
        billing_queue_count=billing,
        purchases_count=converted,
        cross_camera_match_rate=j["cross_camera_match_rate"],
        hourly_breakdown=hourly,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /stores/{store_id}/funnel
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{store_id}/funnel",
    response_model=FunnelOut,
    summary="Get conversion funnel (visitor-journey based)",
)
async def get_funnel(
    store_id: str,
    date_filter: Optional[date] = Query(default=None, alias="date"),
    db: AsyncSession = Depends(get_db),
) -> FunnelOut:
    """
    Entry → Zone Engagement → Billing Zone → Converted funnel.

    Shares _compute_journey_funnel() with /metrics — numbers are always identical.
    Each stage = DISTINCT visitor_ids who completed that stage AND all prior stages.
    Hierarchy guaranteed: Purchase <= Billing <= Engagement <= Entry.
    """
    query_date = date_filter or date.today()

    j = await _compute_journey_funnel(db, store_id, query_date)

    entries   = j["entry_count"]
    zone_eng  = j["zone_engagement_count"]
    billing   = j["billing_queue_count"]
    converted = j["purchases_count"]

    _enforce_hierarchy(store_id, entries, zone_eng, billing, converted)

    stages = [
        FunnelStage(stage="ENTRY",               count=entries,   rate=1.0),
        FunnelStage(
            stage="ZONE_ENGAGEMENT",
            count=zone_eng,
            rate=round(zone_eng  / entries,  4) if entries  > 0 else 0.0,
        ),
        FunnelStage(
            stage="BILLING_ZONE_REACHED",
            count=billing,
            rate=round(billing   / zone_eng, 4) if zone_eng > 0 else 0.0,
        ),
        FunnelStage(
            stage="CONVERTED",
            count=converted,
            rate=round(converted / billing,  4) if billing  > 0 else 0.0,
        ),
    ]

    return FunnelOut(store_id=store_id, date=query_date, stages=stages)


# ─────────────────────────────────────────────────────────────────────────────
# GET /stores/{store_id}/ai-summary
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/{store_id}/ai-summary",
    response_model=AiStoreSummaryResponse,
    summary="AI Store Intelligence Summary",
)
async def get_ai_summary(
    store_id: str,
    db: AsyncSession = Depends(get_db),
) -> AiStoreSummaryResponse:
    """
    Returns an AI-generated executive summary of the store's performance.
    """
    summary = await generate_store_summary(store_id, db)
    return AiStoreSummaryResponse(store_id=store_id, **summary)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _live_supplementary(db: AsyncSession, store_id: str, query_date: date) -> dict:
    """Compute staff_count, avg_dwell, total_revenue live from sessions/transactions.

    CF-08: open sessions included via COALESCE(dwell_seconds, NOW() - entry_time).
    """
    conn = await db.connection()
    is_sqlite = conn.dialect.name == "sqlite"

    if is_sqlite:
        q = text("""
            SELECT
                COUNT(DISTINCT CASE WHEN is_staff = 1 THEN session_id END) AS staff_count,
                COALESCE(AVG(CASE WHEN is_staff = 0 THEN
                    COALESCE(dwell_seconds,
                        CAST((strftime('%s', 'now') - strftime('%s', entry_time)) AS REAL))
                END), 0) AS avg_dwell,
                (SELECT COALESCE(SUM(amount), 0) FROM transactions
                 WHERE store_id = :store_id AND DATE(timestamp) = :date_bucket) AS total_revenue
            FROM visitor_sessions
            WHERE store_id = :store_id AND DATE(entry_time) = :date_bucket
        """)
    else:
        q = text("""
            SELECT
                COUNT(DISTINCT session_id) FILTER (WHERE is_staff)       AS staff_count,
                COALESCE(AVG(
                    COALESCE(dwell_seconds,
                        EXTRACT(EPOCH FROM (NOW() - entry_time)))
                ) FILTER (WHERE NOT is_staff), 0)                        AS avg_dwell,
                (SELECT COALESCE(SUM(amount), 0) FROM transactions
                 WHERE store_id = :store_id
                   AND DATE(timestamp AT TIME ZONE 'UTC') = :date_bucket) AS total_revenue
            FROM visitor_sessions
            WHERE store_id = :store_id
              AND DATE(entry_time AT TIME ZONE 'UTC') = :date_bucket
        """)

    res = await db.execute(q, {"store_id": store_id, "date_bucket": query_date})
    row = res.fetchone()
    return {
        "staff_count":   int(row.staff_count   or 0)   if row else 0,
        "avg_dwell":     float(row.avg_dwell    or 0.0) if row else 0.0,
        "total_revenue": float(row.total_revenue or 0.0) if row else 0.0,
    }
