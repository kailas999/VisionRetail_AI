"""GET /health — database and service health check with per-store feed freshness."""
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.schemas import HealthOut, StoreHealthStat

router = APIRouter(tags=["Health"])
settings = get_settings()

STALE_FEED_THRESHOLD_SECONDS = 600  # 10 minutes


@router.get("/health", response_model=HealthOut, summary="Service health check")
async def health(db: AsyncSession = Depends(get_db)) -> HealthOut:
    """
    Check database connectivity and return service status.

    Includes per-store feed freshness:
    - last_event_at: UTC timestamp of the most recent event ingested per store
    - lag_seconds: seconds since that event
    - stale_feed: True if lag > 10 minutes (STALE_FEED warning for on-call engineers)
    """
    # ── DB connectivity check ─────────────────────────────────────────────────
    try:
        await db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    # ── Per-store last event timestamp ────────────────────────────────────────
    store_stats: list[StoreHealthStat] = []
    try:
        result = await db.execute(
            text("""
                SELECT store_id, MAX(timestamp) AS last_event_at
                FROM events
                GROUP BY store_id
                ORDER BY store_id
            """)
        )
        rows = result.fetchall()
        now = datetime.now(timezone.utc)
        for row in rows:
            last_event_at = row.last_event_at
            # Normalise to UTC-aware datetime
            if last_event_at is not None:
                if last_event_at.tzinfo is None:
                    last_event_at = last_event_at.replace(tzinfo=timezone.utc)
                lag = (now - last_event_at).total_seconds()
                stale = lag > STALE_FEED_THRESHOLD_SECONDS
            else:
                lag = None
                stale = True  # No events at all → feed is stale
            store_stats.append(
                StoreHealthStat(
                    store_id=row.store_id,
                    last_event_at=last_event_at,
                    lag_seconds=round(lag, 1) if lag is not None else None,
                    stale_feed=stale,
                )
            )
    except Exception:
        # Non-fatal — DB might not have events table yet (first boot)
        pass

    overall_status = "healthy" if db_status == "healthy" else "degraded"

    return HealthOut(
        status=overall_status,
        database=db_status,
        environment=settings.environment,
        store_stats=store_stats,
    )

