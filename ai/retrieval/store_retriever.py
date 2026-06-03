"""
Retrieval layer — fetches evidence from PostgreSQL for RAG Copilot.

Separated from the LLM client to keep concerns distinct:
  - retrieval.py  → what data to fetch and how to structure it
  - llm_client.py → how to call the LLM
  - copilot_service.py → orchestration

This makes each layer independently testable.
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def fetch_store_evidence(
    db: AsyncSession,
    store_id: str,
    query_date: Optional[date] = None,
) -> dict[str, Any]:
    """
    Retrieve all evidence for a store + date from the database.
    Returns a structured dict with data_coverage count.
    """
    query_date = query_date or date.today()
    evidence: dict[str, Any] = {"data_coverage": 0}

    # Daily metrics
    row = (await db.execute(
        text("SELECT * FROM daily_metrics WHERE store_id=:s AND date_bucket=:d"),
        {"s": store_id, "d": query_date},
    )).fetchone()

    if row:
        evidence["daily_metrics"] = {
            "date": str(query_date),
            "unique_visitors": row.unique_visitors,
            "conversions": row.conversions,
            "conversion_rate_pct": round(row.conversion_rate * 100, 1),
            "avg_dwell_minutes": round(row.avg_dwell_seconds / 60, 1),
            "peak_hour": row.peak_hour,
            "max_queue_depth": row.max_queue_depth,
            "abandonment_count": row.abandonment_count,
            "total_revenue": row.total_revenue,
        }
        evidence["data_coverage"] += 1

    # Hourly breakdown
    hourly = (await db.execute(
        text("""
            SELECT hour_bucket, unique_visitors, conversions, max_queue_depth
            FROM hourly_metrics
            WHERE store_id=:s AND DATE(hour_bucket AT TIME ZONE 'UTC')=:d
            ORDER BY hour_bucket
        """),
        {"s": store_id, "d": query_date},
    )).fetchall()

    if hourly:
        evidence["hourly_breakdown"] = [
            {"hour": r.hour_bucket.hour, "visitors": r.unique_visitors,
             "conversions": r.conversions, "queue_depth": r.max_queue_depth}
            for r in hourly
        ]
        evidence["data_coverage"] += 1

    # Active anomalies
    anomalies = (await db.execute(
        text("""
            SELECT anomaly_type, severity, metric_value, baseline_value, z_score
            FROM anomalies WHERE store_id=:s AND is_resolved=false
            ORDER BY detected_at DESC LIMIT 5
        """),
        {"s": store_id},
    )).fetchall()

    if anomalies:
        evidence["active_anomalies"] = [
            {"type": r.anomaly_type, "severity": r.severity,
             "metric_value": r.metric_value, "baseline_value": r.baseline_value,
             "z_score": round(r.z_score, 2)}
            for r in anomalies
        ]
        evidence["data_coverage"] += 1

    # Funnel
    funnel = (await db.execute(
        text("""
            SELECT
              COUNT(DISTINCT session_id) FILTER (WHERE event_type='ENTRY' AND is_staff=false) AS entries,
              COUNT(DISTINCT session_id) FILTER (WHERE event_type='ZONE_ENTER' AND is_staff=false) AS zone_enters,
              COUNT(DISTINCT session_id) FILTER (WHERE event_type='BILLING_QUEUE_ABANDON' AND is_staff=false) AS abandoned
            FROM events
            WHERE store_id=:s AND DATE(timestamp AT TIME ZONE 'UTC')=:d
        """),
        {"s": store_id, "d": query_date},
    )).fetchone()

    if funnel and funnel.entries:
        evidence["funnel"] = {
            "entries": funnel.entries or 0,
            "zone_engagements": funnel.zone_enters or 0,
            "queue_abandonments": funnel.abandoned or 0,
        }
        evidence["data_coverage"] += 1

    return evidence


def build_context_string(store_id: str, question: str, evidence: dict, query_date: date) -> str:
    """Serialize evidence to a compact JSON string for the LLM prompt."""
    ctx = {
        "store_id": store_id,
        "analysis_date": str(query_date),
        "question": question,
        "evidence": {k: v for k, v in evidence.items() if k != "data_coverage"},
    }
    return json.dumps(ctx, indent=2, default=str)
