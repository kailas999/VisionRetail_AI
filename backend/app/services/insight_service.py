"""
Anomaly Insight Service — GPT-5.2 explanations for detected anomalies.

Design:
- GPT is used ONLY for root-cause explanation and recommendations.
- All detection, thresholds, z-scores, and business metrics remain
  deterministic (computed in anomaly.py and aggregation.py).
- 15-minute in-process TTLCache prevents redundant API calls.
- On any OpenAI failure the service returns rule-based fallback text
  and marks the response with fallback=True so the UI can indicate
  that AI insights are temporarily unavailable.
- Cache key: "insight:{anomaly_id}" — one entry per anomaly.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from cachetools import TTLCache

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ai.prompts.insight_prompts import INSIGHT_SYSTEM_PROMPT, INSIGHT_USER_TEMPLATE, STORE_SUMMARY_SYSTEM_PROMPT, STORE_SUMMARY_USER_TEMPLATE
from ai.llm_client import chat_completion
from app.utils.logging import get_logger

logger = get_logger(__name__)

# ── 15-minute TTL in-process cache ───────────────────────────────────────────
# maxsize=512 → at most 512 anomaly insights cached simultaneously.
_insight_cache: TTLCache = TTLCache(maxsize=512, ttl=900)  # 900s = 15 min

# ── Metric labels for prompt clarity ─────────────────────────────────────────
_METRIC_LABELS: dict[str, str] = {
    "QUEUE_SPIKE": "Queue Depth",
    "CONVERSION_DROP": "Conversion Rate",
    "TRAFFIC_DROP": "Unique Visitors",
    "DEAD_ZONE": "Zone Visitor Count",
}

# ── Rule-based fallback recommendations (never hallucinated) ─────────────────
_FALLBACK_INSIGHTS: dict[str, dict[str, Any]] = {
    "QUEUE_SPIKE": {
        "root_cause": (
            "Queue depth has exceeded the 7-day same-hour baseline by a statistically "
            "significant margin, indicating sudden demand surge or reduced checkout throughput."
        ),
        "business_impact": (
            "Extended wait times increase abandonment risk and reduce overall conversion rate."
        ),
        "recommended_actions": [
            "Open additional checkout counters immediately.",
            "Deploy floor staff to direct customers to the shortest queue.",
            "If available, activate self-checkout lanes.",
        ],
        "priority_level": "HIGH",
    },
    "CONVERSION_DROP": {
        "root_cause": (
            "Conversion rate is significantly below the historical same-hour average, "
            "suggesting a friction point between zone engagement and purchase completion."
        ),
        "business_impact": (
            "Lower conversion directly reduces revenue per visitor and degrades ROI on footfall."
        ),
        "recommended_actions": [
            "Check billing zone accessibility and staffing levels.",
            "Review recent pricing or promotional changes in high-traffic zones.",
            "Inspect for product stockouts that may deter purchase intent.",
        ],
        "priority_level": "HIGH",
    },
    "TRAFFIC_DROP": {
        "root_cause": (
            "Unique visitor count is significantly below the 7-day same-hour baseline, "
            "pointing to a footfall collapse that may stem from external or entry-point issues."
        ),
        "business_impact": (
            "Reduced footfall compresses the opportunity base for conversions and revenue."
        ),
        "recommended_actions": [
            "Verify store signage and entry are unobstructed.",
            "Check for any physical blockages or access issues at the entrance.",
            "Review recent marketing coverage for gaps.",
        ],
        "priority_level": "MEDIUM",
    },
    "DEAD_ZONE": {
        "root_cause": (
            "Zone visitor count has collapsed relative to the 7-day baseline, "
            "indicating customers are actively avoiding this area."
        ),
        "business_impact": (
            "Under-trafficked zones reduce product exposure and cannibalize overall dwell time."
        ),
        "recommended_actions": [
            "Inspect the zone for physical blockages or poor lighting.",
            "Review planogram — product placement may be repelling traffic.",
            "Reposition promotional displays to re-attract customer flow.",
        ],
        "priority_level": "MEDIUM",
    },
}


def _cache_key(anomaly_id: str) -> str:
    return f"insight:{anomaly_id}"


def _get_cached(anomaly_id: str) -> Optional[dict[str, Any]]:
    return _insight_cache.get(_cache_key(anomaly_id))


def _set_cached(anomaly_id: str, insight: dict[str, Any]) -> None:
    _insight_cache[_cache_key(anomaly_id)] = insight


def _fallback(anomaly_type: str, reason: str = "openai_unavailable") -> dict[str, Any]:
    """Return rule-based insight when OpenAI is unavailable."""
    base = _FALLBACK_INSIGHTS.get(
        anomaly_type,
        {
            "root_cause": "An anomaly was detected that deviates significantly from the historical baseline.",
            "business_impact": "Operations may be impacted — manual inspection is recommended.",
            "recommended_actions": [
                "Investigate the flagged store area.",
                "Consult with floor management.",
                "Monitor metrics for the next 30 minutes.",
            ],
            "priority_level": "MEDIUM",
        },
    )
    return {**base, "fallback": True, "fallback_reason": reason}


def build_prompt_context(anomaly: dict[str, Any]) -> str:
    """
    Build the user message for GPT from a deterministic anomaly dict.
    All numeric values come from the database — GPT receives facts, not raw data.
    """
    anomaly_type: str = anomaly.get("anomaly_type", "UNKNOWN")
    metric_label = _METRIC_LABELS.get(anomaly_type, "Metric Value")

    metric_value = anomaly.get("metric_value", 0.0)
    baseline_value = anomaly.get("baseline_value", 0.0)

    # Conversion rate formatted as percentage if relevant
    if anomaly_type == "CONVERSION_DROP":
        metric_display = f"{metric_value * 100:.1f}%"
        baseline_display = f"{baseline_value * 100:.1f}%"
    else:
        metric_display = f"{metric_value:.1f}"
        baseline_display = f"{baseline_value:.1f}"

    # Conversion rate context (always deterministic — from anomaly record)
    conversion_rate = anomaly.get("conversion_rate")
    conversion_str = f"{conversion_rate * 100:.1f}%" if conversion_rate is not None else "N/A"

    # Detected at
    detected_at = anomaly.get("detected_at")
    if isinstance(detected_at, datetime):
        detected_str = detected_at.strftime("%Y-%m-%d %H:%M UTC")
    else:
        detected_str = str(detected_at) if detected_at else "Unknown"

    # Trend summary (purely textual, derived from deterministic metric delta)
    delta_pct = (
        ((metric_value - baseline_value) / max(abs(baseline_value), 1e-6)) * 100
    )
    direction = "above" if delta_pct > 0 else "below"
    trend_summary = (
        f"Current value is {abs(delta_pct):.0f}% {direction} the 7-day same-hour average "
        f"(z-score {anomaly.get('z_score', 0.0):.2f})."
    )

    return INSIGHT_USER_TEMPLATE.format(
        store_id=anomaly.get("store_id", "Unknown"),
        anomaly_type=anomaly_type,
        severity=anomaly.get("severity", "MEDIUM"),
        detected_at=detected_str,
        metric_label=metric_label,
        metric_value=metric_display,
        baseline_value=baseline_display,
        z_score=f"{anomaly.get('z_score', 0.0):.2f}",
        affected_zone=anomaly.get("affected_zone_id") or "Store-wide",
        conversion_rate=conversion_str,
        trend_summary=trend_summary,
    )


async def generate_insight(anomaly: dict[str, Any]) -> dict[str, Any]:
    """
    Generate an AI insight for an anomaly.

    Flow:
    1. Check TTL cache → return if hit.
    2. Build prompt from deterministic anomaly data.
    3. Call GPT-5.2 with JSON output mode.
    4. Validate response shape.
    5. Cache and return the insight.
    6. On any failure → return rule-based fallback (fallback=True).
    """
    anomaly_id: str = str(anomaly.get("anomaly_id", ""))
    anomaly_type: str = anomaly.get("anomaly_type", "UNKNOWN")

    # ── 1. Cache hit ──────────────────────────────────────────────────────────
    cached = _get_cached(anomaly_id)
    if cached is not None:
        logger.debug("AI insight cache hit", extra={"anomaly_id": anomaly_id})
        return cached

    # ── 2. Build prompt ───────────────────────────────────────────────────────
    try:
        user_message = build_prompt_context(anomaly)
    except Exception as exc:
        logger.warning(
            "Failed to build insight prompt",
            extra={"anomaly_id": anomaly_id, "error": str(exc)},
        )
        return _fallback(anomaly_type, reason="prompt_build_failed")

    # ── 3. Call GPT-5.2 ────────────────────────────────────────────────────────
    try:
        raw: dict[str, Any] = await chat_completion(
            system_prompt=INSIGHT_SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=512,
            temperature=0.2,
        )
    except Exception as exc:
        logger.error(
            "OpenAI call failed for insight",
            extra={"anomaly_id": anomaly_id, "error": str(exc)},
        )
        return _fallback(anomaly_type, reason="openai_error")

    # If chat_completion returned an INSUFFICIENT_DATA signal it means LLM failed
    if raw.get("insufficient_data") or "INSUFFICIENT_DATA" in str(raw.get("conclusion", "")):
        return _fallback(anomaly_type, reason="llm_unavailable")

    # ── 4. Validate required fields ───────────────────────────────────────────
    required = {"root_cause", "business_impact", "recommended_actions", "priority_level"}
    if not required.issubset(raw.keys()):
        logger.warning(
            "GPT insight missing required fields",
            extra={"anomaly_id": anomaly_id, "received_keys": list(raw.keys())},
        )
        return _fallback(anomaly_type, reason="invalid_response_shape")

    # Normalise priority_level
    priority = raw.get("priority_level", "MEDIUM").upper()
    if priority not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        priority = "MEDIUM"

    insight: dict[str, Any] = {
        "root_cause": str(raw["root_cause"]),
        "business_impact": str(raw["business_impact"]),
        "recommended_actions": list(raw.get("recommended_actions", [])),
        "priority_level": priority,
        "fallback": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # ── 5. Cache for 15 minutes ───────────────────────────────────────────────
    if anomaly_id:
        _set_cached(anomaly_id, insight)
        logger.info(
            "AI insight generated and cached",
            extra={"anomaly_id": anomaly_id, "anomaly_type": anomaly_type, "priority": priority},
        )

    return insight

def _summary_cache_key(store_id: str) -> str:
    return f"store_summary:{store_id}"

async def generate_store_summary(store_id: str, db: AsyncSession) -> dict[str, Any]:
    """
    Generate an AI Store Intelligence Summary.
    15-minute TTL Cache.
    Fetches real metrics for prompt.
    """
    cached = _insight_cache.get(_summary_cache_key(store_id))
    if cached is not None:
        logger.debug("AI store summary cache hit", extra={"store_id": store_id})
        return cached

    # 1. Fetch deterministic metrics
    try:
        from datetime import date
        today = date.today()
        conn = await db.connection()
        is_sqlite = conn.dialect.name == "sqlite"
        date_filter = "DATE(timestamp) = :date_bucket" if is_sqlite else "DATE(timestamp AT TIME ZONE 'UTC') = :date_bucket"
        
        # Metrics query
        if is_sqlite:
            metrics_q = text(f"""
                SELECT 
                    COUNT(DISTINCT session_id) FILTER (WHERE event_type = 'ENTRY' AND is_staff = false) as visitors,
                    COUNT(DISTINCT session_id) FILTER (WHERE event_type = 'ZONE_DWELL' AND is_staff = false) as engagement,
                    COUNT(DISTINCT session_id) FILTER (WHERE event_type = 'PURCHASE' AND is_staff = false) as purchases,
                    COUNT(DISTINCT session_id) FILTER (WHERE event_type = 'BILLING_QUEUE_JOIN' AND is_staff = false) as billing_joins,
                    COALESCE(AVG(CAST(json_extract(metadata_json, '$.dwell_seconds') AS REAL)) FILTER (WHERE event_type = 'ZONE_DWELL' AND is_staff = false), 0) as avg_dwell
                FROM events
                WHERE store_id = :store_id AND {date_filter}
            """)
        else:
            metrics_q = text(f"""
                SELECT 
                    COUNT(DISTINCT session_id) FILTER (WHERE event_type = 'ENTRY' AND is_staff = false) as visitors,
                    COUNT(DISTINCT session_id) FILTER (WHERE event_type = 'ZONE_DWELL' AND is_staff = false) as engagement,
                    COUNT(DISTINCT session_id) FILTER (WHERE event_type = 'PURCHASE' AND is_staff = false) as purchases,
                    COUNT(DISTINCT session_id) FILTER (WHERE event_type = 'BILLING_QUEUE_JOIN' AND is_staff = false) as billing_joins,
                    COALESCE(AVG((metadata_json->>'dwell_seconds')::float) FILTER (WHERE event_type = 'ZONE_DWELL' AND is_staff = false), 0) as avg_dwell
                FROM events
                WHERE store_id = :store_id AND {date_filter}
            """)
        metrics_res = (await db.execute(metrics_q, {"store_id": store_id, "date_bucket": today})).fetchone()
        
        # Zones query
        zone_q = text(f"""
            SELECT 
                zone_id,
                COUNT(DISTINCT session_id) as visitors
            FROM events
            WHERE store_id = :store_id AND event_type = 'ZONE_DWELL' AND is_staff = false AND {date_filter}
            GROUP BY zone_id
            ORDER BY visitors DESC
        """)
        zone_res = (await db.execute(zone_q, {"store_id": store_id, "date_bucket": today})).fetchall()
        
        top_zone = zone_res[0].zone_id if zone_res else "None"
        worst_zone = zone_res[-1].zone_id if zone_res else "None"
        
        # Active anomalies
        anom_q = text("""
            SELECT COUNT(*) FROM anomalies WHERE store_id = :store_id AND is_resolved = false
        """)
        anom_count = (await db.execute(anom_q, {"store_id": store_id})).scalar() or 0

        # Derived
        visitors = metrics_res.visitors or 0
        engagement = metrics_res.engagement or 0
        purchases = metrics_res.purchases or 0
        billing_joins = metrics_res.billing_joins or 0
        conversion_rate = f"{((purchases / billing_joins) * 100):.1f}%" if billing_joins > 0 else "0%"
        avg_dwell = metrics_res.avg_dwell or 0.0

        user_message = STORE_SUMMARY_USER_TEMPLATE.format(
            store_id=store_id,
            visitors=visitors,
            engagement=engagement,
            conversion_rate=conversion_rate,
            purchases=purchases,
            top_zone=top_zone,
            worst_zone=worst_zone,
            avg_dwell_seconds=f"{avg_dwell:.1f}",
            active_anomalies_count=anom_count
        )
    except Exception as exc:
        logger.warning("Failed to build summary prompt", extra={"store_id": store_id, "error": str(exc)})
        return _fallback_summary(store_id, "prompt_build_failed")

    # 2. Call GPT-5.2
    try:
        raw: dict[str, Any] = await chat_completion(
            system_prompt=STORE_SUMMARY_SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=512,
            temperature=0.2,
        )
    except Exception as exc:
        logger.error("OpenAI call failed for summary", extra={"store_id": store_id, "error": str(exc)})
        return _fallback_summary(store_id, "openai_error")

    # 3. Validate
    required = {"executive_summary", "revenue_risk", "top_opportunities", "recommended_actions", "priority_level"}
    if not required.issubset(raw.keys()):
        logger.warning("GPT summary missing required fields", extra={"store_id": store_id, "keys": list(raw.keys())})
        return _fallback_summary(store_id, "invalid_response_shape")

    summary: dict[str, Any] = {
        "executive_summary": str(raw["executive_summary"]),
        "revenue_risk": str(raw["revenue_risk"]),
        "top_opportunities": str(raw["top_opportunities"]),
        "recommended_actions": list(raw.get("recommended_actions", [])),
        "priority_level": str(raw["priority_level"]).upper(),
        "fallback": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    _insight_cache[_summary_cache_key(store_id)] = summary
    return summary

def _fallback_summary(store_id: str, reason: str) -> dict[str, Any]:
    return {
        "executive_summary": f"Store {store_id} is operating with active metrics recorded for today.",
        "revenue_risk": "Unable to dynamically assess revenue risk at this time.",
        "top_opportunities": "Review zone engagement manually in the heatmap.",
        "recommended_actions": ["Monitor dashboard metrics", "Check active anomalies"],
        "priority_level": "MEDIUM",
        "fallback": True,
        "fallback_reason": reason,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

