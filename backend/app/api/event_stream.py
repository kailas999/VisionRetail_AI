"""FastAPI event stream router -- GET /stores/{id}/event-stream"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.schemas import EventStreamResponse
from app.services.event_stream_service import get_event_stream_metrics
from app.utils.logging import get_logger

router = APIRouter(prefix="/stores", tags=["Event Stream"])
logger = get_logger(__name__)


@router.get(
    "/{store_id}/event-stream",
    response_model=EventStreamResponse,
    summary="Retail Event Stream Intelligence",
)
async def get_event_stream(
    store_id: str,
    date_filter: Optional[date] = Query(default=None, alias="date"),
    db: AsyncSession = Depends(get_db),
) -> EventStreamResponse:
    """
    Returns aggregated raw event stream metrics for dashboard visualization.
    Includes Entrance, Zone, Billing, and Re-ID intelligence.
    """
    query_date = date_filter or date.today()
    return await get_event_stream_metrics(db, store_id, query_date)
