"""
Z-score based anomaly detection engine.

Design:
- Uses rolling 7-day same-hour baseline (not fixed thresholds).
- Adapts to store-specific traffic patterns.
- Severity: MEDIUM (|z|>2.5), HIGH (|z|>2.8), CRITICAL (|z|>3.0).
- Each anomaly includes a rule-based recommended_action (not hallucinated).
- Anomalies deduped: only one active anomaly per type per store at a time.

Anomaly types:
1. QUEUE_SPIKE     — queue_depth z > +2.5 (unexpectedly long queue)
2. CONVERSION_DROP — conversion_rate z < -2.5 (below historical average)
3. DEAD_ZONE       — zone_dwell_count z < -3.0 (zone traffic collapsed)
4. TRAFFIC_DROP    — unique_visitors z < -2.5 (overall footfall collapsed)

Tradeoffs:
- Z-score needs N>=7 data points to be meaningful (first week has lower confidence).
- Assumes approximately normal distribution of metrics (reasonable for hourly data).
- Outlier contamination: uses rolling window (7 days) so one spike doesn't
  permanently corrupt the baseline.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Recommended actions (rule-based, grounded in evidence — never hallucinated)
RECOMMENDED_ACTIONS = {
    "QUEUE_SPIKE": (
        "Activate additional checkout counters. "
        "Alert floor staff to direct customers to shortest queue. "
        "Consider opening self-checkout if available."
    ),
    "CONVERSION_DROP": (
        "Review recent in-store promotions and pricing changes. "
        "Check if billing zone is accessible and well-staffed. "
        "Inspect for product stockouts in high-traffic zones."
    ),
    "DEAD_ZONE": (
        "Inspect the zone for physical blockages or lighting issues. "
        "Review planogram — product placement may be driving customers away. "
        "Consider repositioning promotional displays to re-attract traffic."
    ),
    "TRAFFIC_DROP": (
        "Check for external factors: weather, local events, competitor activity. "
        "Verify store signage and entry are visible and unobstructed. "
        "Review recent marketing campaigns for gaps in coverage."
    ),
}


def _compute_zscore(current: float, historical: list[float], min_baseline: int = 3) -> Optional[float]:
    """Compute Z-score of current value against historical window."""
    if len(historical) < min_baseline:
        return None  # Insufficient baseline
    arr = np.array(historical, dtype=float)
    mean = np.mean(arr)
    std = np.std(arr)
    if std < 1e-6:
        if min_baseline == 1:
            # Fallback standard deviation for small sample sizes or identical data
            std = max(1.0, 0.1 * mean)
        else:
            return None  # Zero variance — all values identical
    return (current - mean) / std


def _severity(z: float) -> str:
    abs_z = abs(z)
    if abs_z >= 3.0:
        return "CRITICAL"
    elif abs_z >= 2.8:
        return "HIGH"
    else:
        return "MEDIUM"


def _confidence(z: float, n_points: int) -> float:
    """Confidence decreases with fewer data points and lower |z|."""
    abs_z = min(abs(z), 5.0)
    data_confidence = min(1.0, n_points / 14.0)   # max at 14 days
    z_confidence = (abs_z - 2.5) / 2.5            # 0 at threshold, 1 at |z|=5
    return round(min(1.0, data_confidence * z_confidence), 3)


async def run_anomaly_detection(
    session: AsyncSession,
    store_id: str,
    current_time: Optional[datetime] = None,
    zscore_threshold: Optional[float] = None,
    lookback_days: Optional[int] = None,
) -> list[dict]:
    """
    Run all anomaly checks for a store at the current hour.
    Returns list of newly detected anomalies (inserted into DB).
    """
    from app.config import get_settings
    settings = get_settings()
    if zscore_threshold is None:
        zscore_threshold = settings.anomaly_zscore_high
    if lookback_days is None:
        lookback_days = settings.anomaly_lookback_days

    if current_time is None:
        current_time = datetime.now(timezone.utc)

    current_hour = current_time.replace(minute=0, second=0, microsecond=0)
    lookback_start = current_hour - timedelta(days=lookback_days)
    same_hour = current_hour.hour

    new_anomalies = []

    # ── 1. Fetch current hour metrics ──────────────────────────────────────
    curr_result = await session.execute(
        text("""
            SELECT unique_visitors, conversions, max_queue_depth, avg_dwell_seconds
            FROM hourly_metrics
            WHERE store_id = :store_id AND hour_bucket = :hour_bucket
        """),
        {"store_id": store_id, "hour_bucket": current_hour},
    )
    curr_row = curr_result.fetchone()
    if not curr_row:
        return []  # No data for current hour yet

    # ── 2. Fetch historical same-hour baselines ────────────────────────────
    conn = await session.connection()
    is_sqlite = conn.dialect.name == "sqlite"

    if is_sqlite:
        hist_query = text("""
            SELECT unique_visitors, conversions, max_queue_depth, avg_dwell_seconds
            FROM hourly_metrics
            WHERE store_id = :store_id
              AND CAST(strftime('%H', hour_bucket) AS INTEGER) = :same_hour
              AND hour_bucket >= :lookback_start
              AND hour_bucket < :current_hour
            ORDER BY hour_bucket
        """)
    else:
        hist_query = text("""
            SELECT unique_visitors, conversions, max_queue_depth, avg_dwell_seconds
            FROM hourly_metrics
            WHERE store_id = :store_id
              AND EXTRACT(HOUR FROM hour_bucket) = :same_hour
              AND hour_bucket >= :lookback_start
              AND hour_bucket < :current_hour
            ORDER BY hour_bucket
        """)

    hist_result = await session.execute(
        hist_query,
        {
            "store_id": store_id,
            "same_hour": same_hour,
            "lookback_start": lookback_start,
            "current_hour": current_hour,
        },
    )
    hist_rows = hist_result.fetchall()
    n = len(hist_rows)

    min_baseline = 1 if lookback_days == 1 else 3
    if n < min_baseline:
        logger.debug("Insufficient baseline for anomaly detection", extra={"n": n})
        return []

    # ── 3. Check each anomaly type ─────────────────────────────────────────

    checks = [
        {
            "type": "QUEUE_SPIKE",
            "current": float(curr_row.max_queue_depth or 0),
            "historical": [float(r.max_queue_depth or 0) for r in hist_rows],
            "direction": "high",   # z > threshold = anomalous
        },
        {
            "type": "CONVERSION_DROP",
            "current": (
                float(curr_row.conversions or 0) / max(1, float(curr_row.unique_visitors or 1))
            ),
            "historical": [
                float(r.conversions or 0) / max(1, float(r.unique_visitors or 1))
                for r in hist_rows
            ],
            "direction": "low",    # z < -threshold = anomalous
        },
        {
            "type": "TRAFFIC_DROP",
            "current": float(curr_row.unique_visitors or 0),
            "historical": [float(r.unique_visitors or 0) for r in hist_rows],
            "direction": "low",
        },
    ]

    for check in checks:
        z = _compute_zscore(check["current"], check["historical"], min_baseline=min_baseline)
        if z is None:
            continue

        is_anomalous = (
            (check["direction"] == "high" and z > zscore_threshold)
            or (check["direction"] == "low" and z < -zscore_threshold)
        )

        if not is_anomalous:
            continue

        # Check if same type already active (avoid spam)
        existing = await session.execute(
            text("""
                SELECT anomaly_id FROM anomalies
                WHERE store_id = :store_id
                  AND anomaly_type = :atype
                  AND is_resolved = false
                  AND detected_at >= :since
            """),
            {
                "store_id": store_id,
                "atype": check["type"],
                "since": current_hour - timedelta(hours=2),
            },
        )
        if existing.fetchone():
            continue  # Already have an active anomaly of this type

        anomaly_id = uuid.uuid4()
        baseline = float(np.mean(check["historical"]))
        severity = _severity(z)
        confidence = _confidence(z, n)

        await session.execute(
            text("""
                INSERT INTO anomalies (
                    anomaly_id, store_id, detected_at, anomaly_type,
                    severity, confidence, metric_value, baseline_value,
                    z_score, recommended_action, is_resolved
                ) VALUES (
                    :anomaly_id, :store_id, :detected_at, :atype,
                    :severity, :confidence, :metric_value, :baseline,
                    :z_score, :action, false
                )
            """),
            {
                "anomaly_id": anomaly_id,
                "store_id": store_id,
                "detected_at": current_time,
                "atype": check["type"],
                "severity": severity,
                "confidence": confidence,
                "metric_value": check["current"],
                "baseline": baseline,
                "z_score": round(z, 4),
                "action": RECOMMENDED_ACTIONS[check["type"]],
            },
        )

        new_anomalies.append({
            "anomaly_id": str(anomaly_id),
            "type": check["type"],
            "severity": severity,
            "z_score": round(z, 4),
            "metric_value": check["current"],
            "baseline_value": baseline,
        })

        logger.info(
            "Anomaly detected",
            extra={
                "type": check["type"],
                "severity": severity,
                "z_score": round(z, 4),
                "store_id": store_id,
            },
        )

    # ── 4. DEAD_ZONE check — zone with no visits in 30 min ─────────────────
    # This is a time-based check (not z-score), triggered independently of historical baseline.
    dead_zone_threshold = current_time - timedelta(minutes=30)

    if is_sqlite:
        zone_activity_q = text("""
            SELECT z.zone_id, MAX(e.timestamp) AS last_event_at
            FROM zones z
            LEFT JOIN events e
                ON e.zone_id = z.zone_id
               AND e.store_id = z.store_id
               AND e.is_staff = 0
               AND e.event_type IN ('ZONE_ENTER', 'ZONE_DWELL')
            WHERE z.store_id = :store_id
              AND z.zone_type NOT IN ('ENTRY', 'BILLING')
            GROUP BY z.zone_id
        """)
    else:
        zone_activity_q = text("""
            SELECT z.zone_id, MAX(e.timestamp) AS last_event_at
            FROM zones z
            LEFT JOIN events e
                ON e.zone_id = z.zone_id
               AND e.store_id = z.store_id
               AND e.is_staff = false
               AND e.event_type IN ('ZONE_ENTER', 'ZONE_DWELL')
            WHERE z.store_id = :store_id
              AND z.zone_type NOT IN ('ENTRY', 'BILLING')
            GROUP BY z.zone_id
        """)

    zone_result = await session.execute(zone_activity_q, {"store_id": store_id})
    zone_rows = zone_result.fetchall()

    for zone_row in zone_rows:
        zone_id = zone_row.zone_id
        last_event_at = zone_row.last_event_at

        # Normalise timezone
        if last_event_at is not None and hasattr(last_event_at, "tzinfo") and last_event_at.tzinfo is None:
            last_event_at = last_event_at.replace(tzinfo=timezone.utc)

        # Dead zone: no events at all today OR last event was > 30 min ago
        is_dead = (last_event_at is None) or (last_event_at < dead_zone_threshold)
        if not is_dead:
            continue

        # Deduplicate: skip if already an active DEAD_ZONE anomaly for this zone
        existing_dead = await session.execute(
            text("""
                SELECT anomaly_id FROM anomalies
                WHERE store_id = :store_id
                  AND anomaly_type = 'DEAD_ZONE'
                  AND affected_zone_id = :zone_id
                  AND is_resolved = false
                  AND detected_at >= :since
            """),
            {
                "store_id": store_id,
                "zone_id": zone_id,
                "since": current_hour - timedelta(hours=1),
            },
        )
        if existing_dead.fetchone():
            continue

        # Compute lag in minutes for metric_value
        lag_minutes = (
            (current_time - last_event_at).total_seconds() / 60.0
            if last_event_at is not None else 999.0
        )
        anomaly_id = uuid.uuid4()

        await session.execute(
            text("""
                INSERT INTO anomalies (
                    anomaly_id, store_id, detected_at, anomaly_type,
                    severity, confidence, metric_value, baseline_value,
                    z_score, affected_zone_id, recommended_action, is_resolved
                ) VALUES (
                    :anomaly_id, :store_id, :detected_at, 'DEAD_ZONE',
                    'WARN', 0.9, :metric_value, 30.0,
                    0.0, :zone_id, :action, false
                )
            """),
            {
                "anomaly_id": anomaly_id,
                "store_id": store_id,
                "detected_at": current_time,
                "metric_value": round(lag_minutes, 1),
                "zone_id": zone_id,
                "action": RECOMMENDED_ACTIONS["DEAD_ZONE"],
            },
        )

        new_anomalies.append({
            "anomaly_id": str(anomaly_id),
            "type": "DEAD_ZONE",
            "severity": "WARN",
            "z_score": 0.0,
            "metric_value": round(lag_minutes, 1),
            "baseline_value": 30.0,
            "affected_zone_id": zone_id,
        })

        logger.info(
            "DEAD_ZONE anomaly detected",
            extra={"zone_id": zone_id, "lag_minutes": round(lag_minutes, 1), "store_id": store_id},
        )

    return new_anomalies



async def get_active_anomalies(
    session: AsyncSession,
    store_id: str,
) -> list[dict]:
    """Fetch all unresolved anomalies for a store."""
    result = await session.execute(
        text("""
            SELECT anomaly_id, detected_at, anomaly_type, severity,
                   confidence, metric_value, baseline_value, z_score,
                   affected_zone_id, recommended_action, is_resolved
            FROM anomalies
            WHERE store_id = :store_id AND is_resolved = false
            ORDER BY detected_at DESC
        """),
        {"store_id": store_id},
    )
    rows = result.fetchall()
    return [
        {
            "anomaly_id": str(r.anomaly_id),
            "store_id": store_id,
            "detected_at": r.detected_at,
            "anomaly_type": r.anomaly_type,
            "severity": r.severity,
            "confidence": r.confidence,
            "metric_value": r.metric_value,
            "baseline_value": r.baseline_value,
            "z_score": r.z_score,
            "affected_zone_id": r.affected_zone_id,
            "suggested_action": r.recommended_action,
            "is_resolved": r.is_resolved,
        }
        for r in rows
    ]
