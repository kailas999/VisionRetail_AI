"""
Aggregation engine — updates pre-aggregated hourly/daily metrics.

Called after every ingestion batch (synchronously, not scheduled).

Uses PostgreSQL UPSERT (INSERT ... ON CONFLICT DO UPDATE) so:
- No double-counting on re-ingest.
- No separate background job needed.
- Metrics always consistent with events table.

Metrics computed:
- unique_visitors: count distinct non-staff sessions in hour
- conversions: count is_converted sessions
- avg_dwell_seconds: average session dwell
- max_queue_depth: max queue_depth from BILLING_QUEUE_JOIN events
- abandonment_count: count BILLING_QUEUE_ABANDON events
"""
from __future__ import annotations

import logging
import json
from datetime import datetime, date, timezone, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def update_hourly_metrics(
    session: AsyncSession,
    store_id: str,
    hour_bucket: datetime,
) -> None:
    """Recompute and upsert metrics for a specific store+hour."""
    hour_start = hour_bucket.replace(minute=0, second=0, microsecond=0)
    hour_end = hour_start + timedelta(hours=1)

    # Compute from events + sessions in one SQL pass
    conn = await session.connection()
    is_sqlite = conn.dialect.name == "sqlite"

    if is_sqlite:
        query = text("""
            WITH session_stats AS (
                SELECT
                    COUNT(DISTINCT vs.session_id)
                        FILTER (WHERE NOT vs.is_staff) AS unique_visitors,
                    COUNT(DISTINCT vs.session_id)
                        FILTER (WHERE NOT vs.is_staff AND vs.is_staff = 0) AS staff_count,
                    COUNT(DISTINCT vs.session_id)
                        FILTER (WHERE NOT vs.is_staff AND vs.is_converted) AS conversions,
                    AVG(
                        COALESCE(vs.dwell_seconds,
                            CAST((strftime('%s', 'now') - strftime('%s', vs.entry_time)) AS REAL))
                    ) FILTER (WHERE NOT vs.is_staff) AS avg_dwell,
                    COUNT(DISTINCT vs.session_id)
                        FILTER (WHERE vs.is_reentry) AS reentry_count
                FROM visitor_sessions vs
                WHERE vs.store_id = :store_id
                  AND vs.entry_time >= :hour_start
                  AND vs.entry_time < :hour_end
            ),
            queue_stats AS (
                SELECT
                    COALESCE(MAX(CAST(json_extract(e.metadata_json, '$.queue_depth') AS INTEGER)), 0) AS max_queue_depth,
                    COUNT(*) FILTER (WHERE e.event_type = 'BILLING_QUEUE_ABANDON') AS abandonment_count
                FROM events e
                WHERE e.store_id = :store_id
                  AND e.timestamp >= :hour_start
                  AND e.timestamp < :hour_end
                  AND e.event_type IN ('BILLING_QUEUE_JOIN', 'BILLING_QUEUE_ABANDON')
            ),
            revenue_stats AS (
                SELECT COALESCE(SUM(t.amount), 0) AS total_revenue
                FROM transactions t
                WHERE t.store_id = :store_id
                  AND t.timestamp >= :hour_start
                  AND t.timestamp < :hour_end
            )
            SELECT
                ss.unique_visitors,
                ss.staff_count,
                ss.conversions,
                COALESCE(ss.avg_dwell, 0) AS avg_dwell_seconds,
                qs.max_queue_depth,
                qs.abandonment_count,
                ss.reentry_count,
                rs.total_revenue
            FROM session_stats ss, queue_stats qs, revenue_stats rs
        """)
    else:
        query = text("""
            WITH session_stats AS (
                SELECT
                    COUNT(DISTINCT vs.session_id)
                        FILTER (WHERE NOT vs.is_staff) AS unique_visitors,
                    COUNT(DISTINCT vs.session_id)
                        FILTER (WHERE NOT vs.is_staff AND vs.is_staff = false) AS staff_count,
                    COUNT(DISTINCT vs.session_id)
                        FILTER (WHERE NOT vs.is_staff AND vs.is_converted) AS conversions,
                    AVG(
                        COALESCE(vs.dwell_seconds,
                            EXTRACT(EPOCH FROM (NOW() - vs.entry_time)))
                    ) FILTER (WHERE NOT vs.is_staff) AS avg_dwell,
                    COUNT(DISTINCT vs.session_id)
                        FILTER (WHERE vs.is_reentry) AS reentry_count
                FROM visitor_sessions vs
                WHERE vs.store_id = :store_id
                  AND vs.entry_time >= :hour_start
                  AND vs.entry_time < :hour_end
            ),
            queue_stats AS (
                SELECT
                    COALESCE(MAX((e.metadata_json->>'queue_depth')::int), 0) AS max_queue_depth,
                    COUNT(*) FILTER (WHERE e.event_type = 'BILLING_QUEUE_ABANDON') AS abandonment_count
                FROM events e
                WHERE e.store_id = :store_id
                  AND e.timestamp >= :hour_start
                  AND e.timestamp < :hour_end
                  AND e.event_type IN ('BILLING_QUEUE_JOIN', 'BILLING_QUEUE_ABANDON')
            ),
            revenue_stats AS (
                SELECT COALESCE(SUM(t.amount), 0) AS total_revenue
                FROM transactions t
                WHERE t.store_id = :store_id
                  AND t.timestamp >= :hour_start
                  AND t.timestamp < :hour_end
            )
            SELECT
                ss.unique_visitors,
                ss.staff_count,
                ss.conversions,
                COALESCE(ss.avg_dwell, 0) AS avg_dwell_seconds,
                qs.max_queue_depth,
                qs.abandonment_count,
                ss.reentry_count,
                rs.total_revenue
            FROM session_stats ss, queue_stats qs, revenue_stats rs
        """)

    result = await session.execute(
        query,
        {
            "store_id": store_id,
            "hour_start": hour_start,
            "hour_end": hour_end,
        },
    )
    row = result.fetchone()
    if not row:
        return

    now_ts = datetime.now(timezone.utc)
    await session.execute(
        text("""
            INSERT INTO hourly_metrics (
                store_id, hour_bucket, unique_visitors, staff_count,
                conversions, avg_dwell_seconds, max_queue_depth,
                abandonment_count, reentry_count, total_revenue, updated_at,
                zone_dwell_json
            ) VALUES (
                :store_id, :hour_bucket, :unique_visitors, :staff_count,
                :conversions, :avg_dwell, :max_queue, :abandonments,
                :reentries, :revenue, :updated_at,
                CAST(:zone_dwell AS jsonb)
            )
            ON CONFLICT (store_id, hour_bucket)
            DO UPDATE SET
                unique_visitors = EXCLUDED.unique_visitors,
                staff_count = EXCLUDED.staff_count,
                conversions = EXCLUDED.conversions,
                avg_dwell_seconds = EXCLUDED.avg_dwell_seconds,
                max_queue_depth = EXCLUDED.max_queue_depth,
                abandonment_count = EXCLUDED.abandonment_count,
                reentry_count = EXCLUDED.reentry_count,
                total_revenue = EXCLUDED.total_revenue,
                updated_at = EXCLUDED.updated_at
        """),
        {
            "store_id": store_id,
            "hour_bucket": hour_start,
            "unique_visitors": row.unique_visitors or 0,
            "staff_count": row.staff_count or 0,
            "conversions": row.conversions or 0,
            "avg_dwell": float(row.avg_dwell_seconds or 0),
            "max_queue": row.max_queue_depth or 0,
            "abandonments": row.abandonment_count or 0,
            "reentries": row.reentry_count or 0,
            "revenue": float(row.total_revenue or 0),
            "updated_at": now_ts,
            "zone_dwell": "{}",
        },
    )
    logger.debug(
        "Hourly metrics updated",
        extra={"store_id": store_id, "hour": hour_start.isoformat()},
    )


async def update_daily_metrics(
    session: AsyncSession,
    store_id: str,
    date_bucket: date,
) -> None:
    """Recompute and upsert daily metrics by aggregating hourly_metrics rows."""
    conn = await session.connection()
    is_sqlite = conn.dialect.name == "sqlite"

    if is_sqlite:
        query = text("""
            SELECT
                COALESCE(SUM(unique_visitors), 0) AS unique_visitors,
                COALESCE(SUM(staff_count), 0) AS staff_count,
                COALESCE(SUM(conversions), 0) AS conversions,
                COALESCE(AVG(avg_dwell_seconds), 0) AS avg_dwell_seconds,
                COALESCE(MAX(max_queue_depth), 0) AS max_queue_depth,
                COALESCE(SUM(abandonment_count), 0) AS abandonment_count,
                COALESCE(SUM(reentry_count), 0) AS reentry_count,
                COALESCE(SUM(total_revenue), 0) AS total_revenue,
                (
                    SELECT CAST(strftime('%H', hour_bucket) AS INTEGER)
                    FROM hourly_metrics
                    WHERE store_id = :store_id
                      AND DATE(hour_bucket) = :date_bucket
                    ORDER BY unique_visitors DESC
                    LIMIT 1
                ) AS peak_hour
            FROM hourly_metrics
            WHERE store_id = :store_id
              AND DATE(hour_bucket) = :date_bucket
        """)
    else:
        query = text("""
            SELECT
                COALESCE(SUM(unique_visitors), 0) AS unique_visitors,
                COALESCE(SUM(staff_count), 0) AS staff_count,
                COALESCE(SUM(conversions), 0) AS conversions,
                COALESCE(AVG(avg_dwell_seconds), 0) AS avg_dwell_seconds,
                COALESCE(MAX(max_queue_depth), 0) AS max_queue_depth,
                COALESCE(SUM(abandonment_count), 0) AS abandonment_count,
                COALESCE(SUM(reentry_count), 0) AS reentry_count,
                COALESCE(SUM(total_revenue), 0) AS total_revenue,
                (
                    SELECT EXTRACT(HOUR FROM hour_bucket)::int
                    FROM hourly_metrics
                    WHERE store_id = :store_id
                      AND DATE(hour_bucket AT TIME ZONE 'UTC') = :date_bucket
                    ORDER BY unique_visitors DESC
                    LIMIT 1
                ) AS peak_hour
            FROM hourly_metrics
            WHERE store_id = :store_id
              AND DATE(hour_bucket AT TIME ZONE 'UTC') = :date_bucket
        """)

    result = await session.execute(
        query,
        {"store_id": store_id, "date_bucket": date_bucket},
    )
    row = result.fetchone()
    if not row:
        return

    unique_v = row.unique_visitors or 0
    conversions = row.conversions or 0
    conversion_rate = conversions / unique_v if unique_v > 0 else 0.0

    now_ts = datetime.now(timezone.utc)
    await session.execute(
        text("""
            INSERT INTO daily_metrics (
                store_id, date_bucket, unique_visitors, staff_count,
                conversions, conversion_rate, avg_dwell_seconds,
                peak_hour, max_queue_depth, abandonment_count,
                reentry_count, total_revenue, updated_at, zone_dwell_json
            ) VALUES (
                :store_id, :date_bucket, :unique_visitors, :staff_count,
                :conversions, :conversion_rate, :avg_dwell,
                :peak_hour, :max_queue, :abandonments,
                :reentries, :revenue, :updated_at, CAST(:zone_dwell AS jsonb)
            )
            ON CONFLICT (store_id, date_bucket)
            DO UPDATE SET
                unique_visitors = EXCLUDED.unique_visitors,
                staff_count = EXCLUDED.staff_count,
                conversions = EXCLUDED.conversions,
                conversion_rate = EXCLUDED.conversion_rate,
                avg_dwell_seconds = EXCLUDED.avg_dwell_seconds,
                peak_hour = EXCLUDED.peak_hour,
                max_queue_depth = EXCLUDED.max_queue_depth,
                abandonment_count = EXCLUDED.abandonment_count,
                reentry_count = EXCLUDED.reentry_count,
                total_revenue = EXCLUDED.total_revenue,
                updated_at = EXCLUDED.updated_at
        """),
        {
            "store_id": store_id,
            "date_bucket": date_bucket,
            "unique_visitors": unique_v,
            "staff_count": row.staff_count or 0,
            "conversions": conversions,
            "conversion_rate": round(conversion_rate, 4),
            "avg_dwell": float(row.avg_dwell_seconds or 0),
            "peak_hour": row.peak_hour,
            "max_queue": row.max_queue_depth or 0,
            "abandonments": row.abandonment_count or 0,
            "reentries": row.reentry_count or 0,
            "revenue": float(row.total_revenue or 0),
            "updated_at": now_ts,
            "zone_dwell": "{}",
        },
    )
    logger.debug(
        "Daily metrics updated",
        extra={"store_id": store_id, "date": str(date_bucket)},
    )
