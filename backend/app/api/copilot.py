"""FastAPI Copilot router — POST /copilot/query"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.schemas import CopilotQuery, CopilotResponse, AiStoreSummaryResponse
from app.services.copilot_service import CopilotService
from app.services.insight_service import generate_store_summary
from app.utils.logging import get_logger, request_trace_id

router = APIRouter(prefix="/copilot", tags=["AI Copilot"])
logger = get_logger(__name__)

_copilot_service = CopilotService()


@router.post(
    "/query",
    response_model=CopilotResponse,
    summary="AI Store Intelligence Copilot (RAG + GPT)",
)
async def copilot_query(
    payload: CopilotQuery,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> CopilotResponse:
    """
    GPT-powered store intelligence query with RAG grounding.

    - Retrieves real store metrics, anomalies, funnel data.
    - Grounds GPT response in evidence only.
    - Returns INSUFFICIENT_DATA when evidence is lacking.
    - Never invents explanations.
    """
    trace_id = request_trace_id.get()

    logger.info(
        "Copilot query",
        extra={
            "store_id": payload.store_id,
            "question": payload.question[:100],
            "trace_id": trace_id,
        },
    )

    result = await _copilot_service.query(
        store_id=payload.store_id,
        question=payload.question,
        db_session=db,
        query_date=payload.date,
        trace_id=trace_id,
    )

    return CopilotResponse(**result)


