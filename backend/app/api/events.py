"""FastAPI event ingestion router — POST /events/ingest"""
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.schemas import BatchEventIngest, EventIngestResponse
from app.services.ingestion import ingest_events
from app.services.aggregation import update_hourly_metrics, update_daily_metrics
from app.services.anomaly import run_anomaly_detection
from app.utils.logging import get_logger, request_trace_id

router = APIRouter(prefix="/events", tags=["Events"])
logger = get_logger(__name__)


@router.post(
    "/ingest",
    response_model=EventIngestResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest a batch of events (idempotent)",
)
async def ingest(
    payload: BatchEventIngest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> EventIngestResponse:
    """
    Idempotent batch event ingestion.

    - Duplicate event_ids are silently ignored (HTTP 200, not 409).
    - Returns counts: ingested / duplicates / errors.
    - Triggers hourly/daily metric aggregation after each batch.
    - Triggers anomaly detection run.
    """
    trace_id = request_trace_id.get()

    try:
        # CF-06: Wire Re-ID service from app.state
        reid_service = getattr(request.app.state, "reid_service", None)
        
        result = await ingest_events(db, payload.events, trace_id, reid_service=reid_service)

        # Update aggregations for all affected store+hours
        store_hours: set[tuple] = set()
        for ev in payload.events:
            ts = ev.timestamp
            hour_bucket = ts.replace(minute=0, second=0, microsecond=0)
            store_hours.add((ev.store_id, hour_bucket, ts.date()))

        for store_id, hour_bucket, date_bucket in store_hours:
            await update_hourly_metrics(db, store_id, hour_bucket)
            await update_daily_metrics(db, store_id, date_bucket)
            await run_anomaly_detection(db, store_id)

        return EventIngestResponse(
            ingested=result["ingested"],
            duplicates=result["duplicates"],
            errors=result["errors"],
            trace_id=trace_id,
        )
    except Exception as e:
        logger.exception("Ingestion failed")
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")
