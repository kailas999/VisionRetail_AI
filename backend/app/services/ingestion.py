"""
Idempotent event ingestion service.

Key properties:
- Deduplication: ON CONFLICT DO NOTHING on event_id (UUID PK).
- Batch insert using SQLAlchemy core (faster than ORM for bulk).
- Session upsert: create or update visitor_sessions.
- Triggers aggregation update after each batch.
- Returns counts: ingested / duplicates / errors.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db_models import Event, VisitorSession
from app.models.schemas import EventIngest
from app.utils.logging import get_logger

logger = get_logger(__name__)




async def ingest_events(
    session: AsyncSession,
    events: list[EventIngest],
    trace_id: str,
    reid_service=None,
) -> dict[str, int]:
    """
    Ingest a batch of events idempotently.
    Returns {'ingested': N, 'duplicates': N, 'errors': N}.
    """
    ingested = 0
    duplicates = 0
    errors = 0

    # Detect dialect once — works with both sync-wrapped and native async engines
    try:
        dialect_name = session.bind.dialect.name  # type: ignore[union-attr]
    except AttributeError:
        dialect_name = "postgresql"  # production default
    is_sqlite = dialect_name == "sqlite"

    # ── Ensure store exists (graceful) ──────────────────────────────────────
    store_ids = {e.store_id for e in events}
    for store_id in store_ids:
        await session.execute(
            text("""
                INSERT INTO stores (store_id, name, timezone)
                VALUES (:store_id, :name, :tz)
                ON CONFLICT (store_id) DO NOTHING
            """),
            {"store_id": store_id, "name": store_id, "tz": "Asia/Kolkata"},
        )

    # ── Build event rows ────────────────────────────────────────────────────
    event_rows: list[dict[str, Any]] = []
    session_updates: dict[str, dict] = {}  # visitor_id → session data

    for ev in events:
        # Extract session_seq from metadata as per spec
        seq = 0
        if ev.metadata and "session_seq" in ev.metadata:
            seq = ev.metadata["session_seq"]

        # Resolve identity via Re-ID
        if reid_service:
            resolved_vid, is_reentry = reid_service.resolve(
                raw_id=ev.visitor_id,
                camera_id=ev.camera_id,
                timestamp=ev.timestamp,
                bbox=ev.metadata.get("bbox") if ev.metadata else None,
            )
        else:
            resolved_vid = ev.visitor_id
            is_reentry = ev.event_type.value == "REENTRY"

        # Use visitor_id, store_id, date, and session_seq to deterministically generate a session UUID
        date_str = ev.timestamp.strftime("%Y-%m-%d")
        sid_str = f"{resolved_vid}:{ev.store_id}:{date_str}:{seq}"
        sid = uuid.uuid5(uuid.NAMESPACE_OID, sid_str)

        event_rows.append({
            "event_id": ev.event_id,
            "store_id": ev.store_id,
            "session_id": sid,
            "visitor_id": resolved_vid,
            "event_type": ev.event_type.value,
            "timestamp": ev.timestamp,
            "zone_id": ev.zone_id,
            "confidence": ev.confidence,
            "is_staff": ev.is_staff,
            "camera_id": ev.camera_id,
            "bbox_json": None,
            "metadata_json": ev.metadata,
            "sequence_number": seq,
        })

        # Track session data for upsert
        key = f"{resolved_vid}:{ev.store_id}:{str(sid)}"
        if key not in session_updates:
            session_updates[key] = {
                "session_id": sid,
                "store_id": ev.store_id,
                "visitor_id": resolved_vid,
                "entry_time": ev.timestamp,
                "is_staff": ev.is_staff,
                "is_reentry": is_reentry,
                "zones_visited": [],
                "track_ids": [],
                "exit_time": None,
                "dwell_seconds": None,
            }
        sess = session_updates[key]
        if ev.event_type.value in ("EXIT",):
            sess["exit_time"] = ev.timestamp
        if ev.zone_id and ev.zone_id not in sess["zones_visited"]:
            sess["zones_visited"].append(ev.zone_id)

    # ── Upsert visitor sessions first (maintains foreign key constraint) ─────
    for sess_data in session_updates.values():
        if is_sqlite:
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            stmt = sqlite_insert(VisitorSession.__table__).values(
                session_id=sess_data["session_id"],  # uuid.UUID – type processor converts to CHAR(36)
                store_id=sess_data["store_id"],
                visitor_id=sess_data["visitor_id"],
                entry_time=sess_data["entry_time"],
                is_staff=sess_data["is_staff"],
                is_reentry=sess_data["is_reentry"],
                zones_visited=sess_data["zones_visited"],
                track_ids=sess_data["track_ids"],
                exit_time=sess_data["exit_time"],
                dwell_seconds=sess_data["dwell_seconds"],
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=["session_id"])
        else:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = pg_insert(VisitorSession.__table__).values(
                session_id=sess_data["session_id"],
                store_id=sess_data["store_id"],
                visitor_id=sess_data["visitor_id"],
                entry_time=sess_data["entry_time"],
                is_staff=sess_data["is_staff"],
                is_reentry=sess_data["is_reentry"],
                zones_visited=sess_data["zones_visited"],
                track_ids=sess_data["track_ids"],
                exit_time=sess_data["exit_time"],
                dwell_seconds=sess_data["dwell_seconds"],
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["session_id"],
                set_={
                    "zones_visited": stmt.excluded.zones_visited,
                    "is_staff": stmt.excluded.is_staff,
                    "exit_time": func.coalesce(stmt.excluded.exit_time, VisitorSession.exit_time),
                    "dwell_seconds": func.coalesce(
                        func.extract('epoch', stmt.excluded.exit_time - VisitorSession.entry_time),
                        VisitorSession.dwell_seconds
                    ),
                },
            )
        await session.execute(stmt)

    # ── Batch insert events second ───────────────────────────────────────────
    if event_rows:
        if is_sqlite:
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert
            stmt = sqlite_insert(Event.__table__).values(event_rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=["event_id"])
        else:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = pg_insert(Event.__table__).values(event_rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=["event_id"])

        result = await session.execute(stmt)
        ingested = result.rowcount
        duplicates = len(event_rows) - ingested

    logger.info(
        "Ingestion complete",
        extra={
            "trace_id": trace_id,
            "ingested": ingested,
            "duplicates": duplicates,
            "errors": errors,
        },
    )
    return {"ingested": ingested, "duplicates": duplicates, "errors": errors}

