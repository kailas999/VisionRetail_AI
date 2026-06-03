"""FastAPI heatmap router -- GET /stores/{id}/heatmap"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.schemas import HeatmapOut, ZoneHeatmapPoint
from app.utils.logging import get_logger

router = APIRouter(prefix="/stores", tags=["Heatmap"])
logger = get_logger(__name__)


@router.get(
    "/{store_id}/heatmap",
    response_model=HeatmapOut,
    summary="Zone dwell-time heatmap",
)
async def get_heatmap(
    store_id: str,
    date_filter: Optional[date] = Query(default=None, alias="date"),
    db: AsyncSession = Depends(get_db),
) -> HeatmapOut:
    """
    Returns per-zone dwell time and visitor count for heatmap visualisation.
    Intensity is normalised to [0,1] relative to the hottest zone.

    Data Source Fallback (CF-03):
    1. Uses ZONE_DWELL events (actual live dwell)
    2. Fallback to ZONE_ENTER events (proxy session dwell) if no ZONE_DWELL exists
    3. Return empty if no events exist (removed seeded daily_metrics fallback)
    """
    query_date = date_filter or date.today()

    # 1. Zone definitions
    zone_result = await db.execute(
        text("""
            SELECT zone_id, name, zone_type, polygon_json
            FROM zones WHERE store_id = :store_id
        """),
        {"store_id": store_id},
    )
    zones = {r.zone_id: r for r in zone_result.fetchall()}

    if not zones:
        return HeatmapOut(store_id=store_id, date=query_date, zones=[], data_source="empty", data_confidence=False)

    conn = await db.connection()
    is_sqlite = conn.dialect.name == "sqlite"

    # 2. Visitor count per zone from all events for that day
    if is_sqlite:
        visitor_query = text("""
            SELECT
                e.zone_id,
                COUNT(DISTINCT e.session_id) AS visitor_count
            FROM events e
            WHERE e.store_id = :store_id
              AND e.is_staff = 0
              AND e.zone_id IS NOT NULL
              AND DATE(e.timestamp) = :date_bucket
            GROUP BY e.zone_id
        """)
    else:
        visitor_query = text("""
            SELECT
                e.zone_id,
                COUNT(DISTINCT e.session_id) AS visitor_count
            FROM events e
            WHERE e.store_id = :store_id
              AND e.is_staff = false
              AND e.zone_id IS NOT NULL
              AND DATE(e.timestamp AT TIME ZONE 'UTC') = :date_bucket
            GROUP BY e.zone_id
        """)
    visitor_result = await db.execute(
        visitor_query,
        {"store_id": store_id, "date_bucket": query_date},
    )
    visitor_rows = {r.zone_id: int(r.visitor_count) for r in visitor_result.fetchall()}

    # 3. Avg dwell from ZONE_DWELL events (preferred)
    if is_sqlite:
        dwell_query = text("""
            SELECT
                e.zone_id,
                AVG(CAST(json_extract(e.metadata_json, '$.dwell_seconds') AS REAL)) AS avg_dwell
            FROM events e
            WHERE e.store_id = :store_id
              AND e.is_staff = 0
              AND e.zone_id IS NOT NULL
              AND e.event_type = 'ZONE_DWELL'
              AND DATE(e.timestamp) = :date_bucket
            GROUP BY e.zone_id
        """)
    else:
        dwell_query = text("""
            SELECT
                e.zone_id,
                AVG((e.metadata_json->>'dwell_seconds')::float) AS avg_dwell
            FROM events e
            WHERE e.store_id = :store_id
              AND e.is_staff = false
              AND e.zone_id IS NOT NULL
              AND e.event_type = 'ZONE_DWELL'
              AND DATE(e.timestamp AT TIME ZONE 'UTC') = :date_bucket
            GROUP BY e.zone_id
        """)
    dwell_result = await db.execute(
        dwell_query,
        {"store_id": store_id, "date_bucket": query_date},
    )
    dwell_rows: dict[str, float] = {
        r.zone_id: float(r.avg_dwell or 0) for r in dwell_result.fetchall() if r.avg_dwell is not None
    }
    
    data_source = "live_dwell"

    # 4. Fallback: Proxy dwell time using ZONE_ENTER and session dwell
    # 4. Fallback avg dwell from ZONE_ENTER proxy if no ZONE_DWELL events exist
    fallback_query = text("""
        WITH enter_events AS (
            SELECT session_id, zone_id, MIN(timestamp) as enter_t
            FROM events
            WHERE store_id = :store_id AND event_type = 'ZONE_ENTER' AND zone_id IS NOT NULL
            GROUP BY session_id, zone_id
        ),
        exit_events AS (
            SELECT session_id, MAX(timestamp) as exit_t
            FROM events
            WHERE store_id = :store_id AND event_type IN ('ZONE_EXIT', 'EXIT', 'PURCHASE')
            GROUP BY session_id
        )
        SELECT
            en.zone_id,
            AVG(EXTRACT(EPOCH FROM (ex.exit_t - en.enter_t))) AS avg_dwell
        FROM enter_events en
        JOIN exit_events ex ON en.session_id = ex.session_id
        WHERE ex.exit_t > en.enter_t
        GROUP BY en.zone_id
    """ if not is_sqlite else """
        WITH enter_events AS (
            SELECT session_id, zone_id, MIN(timestamp) as enter_t
            FROM events
            WHERE store_id = :store_id AND event_type = 'ZONE_ENTER' AND zone_id IS NOT NULL
            GROUP BY session_id, zone_id
        ),
        exit_events AS (
            SELECT session_id, MAX(timestamp) as exit_t
            FROM events
            WHERE store_id = :store_id AND event_type IN ('ZONE_EXIT', 'EXIT', 'PURCHASE')
            GROUP BY session_id
        )
        SELECT
            en.zone_id,
            AVG((julianday(ex.exit_t) - julianday(en.enter_t)) * 86400.0) AS avg_dwell
        FROM enter_events en
        JOIN exit_events ex ON en.session_id = ex.session_id
        WHERE ex.exit_t > en.enter_t
        GROUP BY en.zone_id
    """)

    fallback_result = await db.execute(fallback_query, {"store_id": store_id})
    fallback_rows = {r.zone_id: float(r.avg_dwell) for r in fallback_result.fetchall()}

    # 5. Zone Enter and Exit Counts
    date_filter_str = "DATE(e.timestamp) = :date_bucket" if is_sqlite else "DATE(e.timestamp AT TIME ZONE 'UTC') = :date_bucket"
    counts_query = text(f"""
        SELECT 
            e.zone_id,
            COUNT(*) FILTER (WHERE e.event_type = 'ZONE_ENTER') as enter_count,
            COUNT(*) FILTER (WHERE e.event_type = 'ZONE_EXIT') as exit_count
        FROM events e
        WHERE e.store_id = :store_id 
          AND e.is_staff = false 
          AND e.zone_id IS NOT NULL
          AND {date_filter_str}
        GROUP BY e.zone_id
    """)
    counts_result = await db.execute(counts_query, {"store_id": store_id, "date_bucket": query_date})
    counts_rows = {r.zone_id: {"enter": r.enter_count or 0, "exit": r.exit_count or 0} for r in counts_result.fetchall()}

    # 6. Count unique sessions to determine data_confidence
    if is_sqlite:
        session_count_q = text("""
            SELECT COUNT(DISTINCT session_id) AS cnt
            FROM events
            WHERE store_id = :store_id
              AND is_staff = 0
              AND DATE(timestamp) = :date_bucket
        """)
    else:
        session_count_q = text("""
            SELECT COUNT(DISTINCT session_id) AS cnt
            FROM events
            WHERE store_id = :store_id
              AND is_staff = false
              AND DATE(timestamp AT TIME ZONE 'UTC') = :date_bucket
        """)
    session_count_result = await db.execute(session_count_q, {"store_id": store_id, "date_bucket": query_date})
    session_count_row = session_count_result.fetchone()
    total_sessions = int(session_count_row.cnt or 0) if session_count_row else 0
    data_confidence = total_sessions >= 20

    # 7. Finalise Normalisation and formatting
    max_dwell = max([*dwell_rows.values(), *fallback_rows.values()], default=1.0) or 1.0

    zone_points = []
    for zone_id, z in zones.items():
        avg_dw = dwell_rows.get(zone_id) or fallback_rows.get(zone_id, 0.0)
        vc = visitor_rows.get(zone_id, 0)
        en_count = counts_rows.get(zone_id, {}).get("enter", 0)
        ex_count = counts_rows.get(zone_id, {}).get("exit", 0)

        zone_points.append(
            ZoneHeatmapPoint(
                zone_id=zone_id,
                zone_name=z.name,
                zone_type=z.zone_type,
                avg_dwell_seconds=round(avg_dw, 1),
                visitor_count=vc,
                zone_enter_count=en_count,
                zone_exit_count=ex_count,
                polygon=z.polygon_json or [],
                intensity=round(avg_dw / max_dwell, 4),
            )
        )

    zone_points.sort(key=lambda z: z.intensity, reverse=True)
    return HeatmapOut(
        store_id=store_id,
        date=query_date,
        zones=zone_points,
        data_source=data_source,
        data_confidence=data_confidence,
    )
