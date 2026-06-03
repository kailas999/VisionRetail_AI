from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.schemas import EventStreamResponse, EntranceStats, ZoneStats, BillingStats, ReidStats


async def get_event_stream_metrics(
    db: AsyncSession,
    store_id: str,
    query_date: date,
) -> EventStreamResponse:
    """
    Fetch and aggregate all event stream metrics strictly from raw events table.
    """
    conn = await db.connection()
    is_sqlite = conn.dialect.name == "sqlite"

    date_filter = "DATE(timestamp) = :date" if is_sqlite else "DATE(timestamp AT TIME ZONE 'UTC') = :date"
    
    # Entrance
    entrance_q = text(f"""
        SELECT 
            COUNT(*) FILTER (WHERE event_type = 'ENTRY') as entry_count,
            COUNT(*) FILTER (WHERE event_type = 'EXIT') as exit_count,
            COUNT(*) FILTER (WHERE event_type = 'REENTRY') as reentry_count
        FROM events
        WHERE store_id = :store_id AND {date_filter}
    """)
    ent_res = (await db.execute(entrance_q, {"store_id": store_id, "date": query_date})).fetchone()
    
    # Zone
    if is_sqlite:
        zone_q = text(f"""
            SELECT 
                COUNT(*) FILTER (WHERE event_type = 'ZONE_ENTER') as zone_enter_count,
                COUNT(*) FILTER (WHERE event_type = 'ZONE_EXIT') as zone_exit_count,
                COUNT(*) FILTER (WHERE event_type = 'ZONE_DWELL') as zone_dwell_count,
                COALESCE(AVG(CAST(json_extract(metadata_json, '$.dwell_seconds') AS REAL)) FILTER (WHERE event_type = 'ZONE_DWELL'), 0) as avg_dwell
            FROM events
            WHERE store_id = :store_id AND {date_filter}
        """)
    else:
        zone_q = text(f"""
            SELECT 
                COUNT(*) FILTER (WHERE event_type = 'ZONE_ENTER') as zone_enter_count,
                COUNT(*) FILTER (WHERE event_type = 'ZONE_EXIT') as zone_exit_count,
                COUNT(*) FILTER (WHERE event_type = 'ZONE_DWELL') as zone_dwell_count,
                COALESCE(AVG((metadata_json->>'dwell_seconds')::float) FILTER (WHERE event_type = 'ZONE_DWELL'), 0) as avg_dwell
            FROM events
            WHERE store_id = :store_id AND {date_filter}
        """)
    zone_res = (await db.execute(zone_q, {"store_id": store_id, "date": query_date})).fetchone()
    avg_dwell = zone_res.avg_dwell or 0.0

    # Billing
    billing_q = text(f"""
        SELECT 
            COUNT(DISTINCT visitor_id) FILTER (WHERE event_type = 'BILLING_QUEUE_JOIN') as queue_join_count,
            COUNT(DISTINCT visitor_id) FILTER (WHERE event_type = 'BILLING_QUEUE_ABANDON') as queue_abandon_count,
            COUNT(DISTINCT visitor_id) FILTER (WHERE event_type = 'PURCHASE') as purchase_count
        FROM events
        WHERE store_id = :store_id AND {date_filter}
    """)
    bill_res = (await db.execute(billing_q, {"store_id": store_id, "date": query_date})).fetchone()
    
    # Re-ID / Cross Camera
    reid_q = text(f"""
        WITH visitor_cameras AS (
            SELECT visitor_id, COUNT(DISTINCT camera_id) as cam_count
            FROM events
            WHERE store_id = :store_id AND {date_filter}
            GROUP BY visitor_id
        )
        SELECT 
            COUNT(*) as total_visitors,
            COUNT(*) FILTER (WHERE cam_count > 1) as cross_camera_matches
        FROM visitor_cameras
    """)
    reid_res = (await db.execute(reid_q, {"store_id": store_id, "date": query_date})).fetchone()
    
    # Avg Confidence
    conf_q = text(f"""
        SELECT COALESCE(AVG(confidence), 0.94) * 100 as avg_confidence
        FROM events
        WHERE store_id = :store_id AND {date_filter}
    """)
    conf_res = (await db.execute(conf_q, {"store_id": store_id, "date": query_date})).fetchone()

    # Derived Entrance Metrics
    entry_c = ent_res.entry_count or 0
    exit_c = ent_res.exit_count or 0
    reentry_c = ent_res.reentry_count or 0
    current_occupancy = max(0, entry_c + reentry_c - exit_c)
    
    entrance_stats = EntranceStats(
        entry_count=entry_c,
        exit_count=exit_c,
        reentry_count=reentry_c,
        current_occupancy=current_occupancy
    )
    
    zone_stats = ZoneStats(
        zone_enter_count=zone_res.zone_enter_count or 0,
        zone_exit_count=zone_res.zone_exit_count or 0,
        zone_dwell_count=zone_res.zone_dwell_count or 0,
        avg_dwell_seconds=float(avg_dwell)
    )
    
    # Derived Billing Metrics
    join_c = bill_res.queue_join_count or 0
    abandon_c = bill_res.queue_abandon_count or 0
    purchase_c = bill_res.purchase_count or 0
    abandon_rate = round((abandon_c / join_c * 100), 1) if join_c > 0 else 0.0
    # Add billing conversion rate (Purchases / Queue Joins)
    billing_conv = round((purchase_c / join_c * 100), 1) if join_c > 0 else 0.0
    
    billing_stats = BillingStats(
        queue_join_count=join_c,
        queue_abandon_count=abandon_c,
        purchase_count=purchase_c,
        queue_abandon_rate=abandon_rate,
        billing_conversion_rate=billing_conv
    )
    
    # Derived Reid Metrics
    total_v = reid_res.total_visitors or 0
    cross_c = reid_res.cross_camera_matches or 0
    match_rate = round((cross_c / total_v * 100), 1) if total_v > 0 else 0.0
    frag_visitors = max(0, total_v - cross_c)
    avg_conf = float(conf_res.avg_confidence)
    
    reid_stats = ReidStats(
        cross_camera_matches=cross_c,
        match_rate=match_rate,
        fragmented_visitors=frag_visitors,
        avg_confidence=round(avg_conf, 1)
    )

    return EventStreamResponse(
        entrance=entrance_stats,
        zone=zone_stats,
        billing=billing_stats,
        reid=reid_stats
    )
