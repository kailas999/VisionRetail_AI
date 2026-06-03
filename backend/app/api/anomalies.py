"""FastAPI anomalies router — GET /stores/{id}/anomalies and insight endpoint."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.schemas import AnomaliesResponse, AnomalyInsight, AnomalyOut
from app.services.anomaly import get_active_anomalies
from app.services.insight_service import generate_insight
from app.utils.logging import get_logger

router = APIRouter(prefix="/stores", tags=["Anomalies"])
logger = get_logger(__name__)


@router.get(
    "/{store_id}/anomalies",
    response_model=AnomaliesResponse,
    summary="Get active anomalies with rule-based recommendations",
)
async def get_anomalies(
    store_id: str,
    db: AsyncSession = Depends(get_db),
) -> AnomaliesResponse:
    """
    Returns all unresolved anomalies for a store.
    Each anomaly includes: type, severity, confidence, z_score, recommended_action.
    All values are deterministic — no AI involved.
    """
    anomalies = await get_active_anomalies(db, store_id)

    return AnomaliesResponse(
        store_id=store_id,
        active_count=len(anomalies),
        anomalies=[AnomalyOut(**a) for a in anomalies],
    )


@router.get(
    "/{store_id}/anomalies/{anomaly_id}/insight",
    response_model=AnomalyInsight,
    summary="Get GPT-5.2 AI insight for a specific anomaly",
)
async def get_anomaly_insight(
    store_id: str,
    anomaly_id: str,
    db: AsyncSession = Depends(get_db),
) -> AnomalyInsight:
    """
    Returns an AI-generated root-cause explanation, business impact, and
    recommended actions for a specific anomaly.

    - Detection is always deterministic (z-score based).
    - GPT-5.2 is ONLY used here for explanation text.
    - Responses are cached 15 minutes per anomaly_id.
    - Falls back to rule-based recommendations if OpenAI is unavailable.
    """
    # ── Fetch the anomaly row ──────────────────────────────────────────────────
    result = await db.execute(
        text("""
            SELECT anomaly_id, store_id, detected_at, anomaly_type,
                   severity, confidence, metric_value, baseline_value,
                   z_score, affected_zone_id, recommended_action
            FROM anomalies
            WHERE store_id = :store_id
              AND CAST(anomaly_id AS TEXT) = :anomaly_id
        """),
        {"store_id": store_id, "anomaly_id": anomaly_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    # ── Fetch current conversion rate for context (deterministic) ────────────
    metrics_result = await db.execute(
        text("""
            SELECT conversions, unique_visitors
            FROM hourly_metrics
            WHERE store_id = :store_id
            ORDER BY hour_bucket DESC
            LIMIT 1
        """),
        {"store_id": store_id},
    )
    metrics_row = metrics_result.fetchone()
    conversion_rate: float | None = None
    if metrics_row and metrics_row.unique_visitors:
        conversion_rate = (
            float(metrics_row.conversions or 0) / float(metrics_row.unique_visitors)
        )

    # ── Build anomaly dict for insight service ────────────────────────────────
    anomaly_dict = {
        "anomaly_id": str(row.anomaly_id),
        "store_id": store_id,
        "detected_at": row.detected_at,
        "anomaly_type": row.anomaly_type,
        "severity": row.severity,
        "confidence": row.confidence,
        "metric_value": float(row.metric_value),
        "baseline_value": float(row.baseline_value),
        "z_score": float(row.z_score),
        "affected_zone_id": row.affected_zone_id,
        "conversion_rate": conversion_rate,
    }

    # ── Generate AI insight (cache-aware, with fallback) ─────────────────────
    insight = await generate_insight(anomaly_dict)

    return AnomalyInsight(
        anomaly_id=anomaly_id,
        store_id=store_id,
        anomaly_type=row.anomaly_type,
        root_cause=insight["root_cause"],
        business_impact=insight["business_impact"],
        recommended_actions=insight.get("recommended_actions", []),
        priority_level=insight.get("priority_level", "MEDIUM"),
        fallback=insight.get("fallback", False),
        fallback_reason=insight.get("fallback_reason"),
        generated_at=insight.get("generated_at"),
    )
