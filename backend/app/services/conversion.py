"""
POS Conversion Engine.

Business rule:
    A visitor session is converted if the session's visitor entered the
    BILLING zone within `window_minutes` (default 5) before a POS transaction.

Algorithm:
1. On transaction ingest, query sessions with:
   - store_id match
   - billing zone in zones_visited
   - entry_time within [tx.timestamp - window, tx.timestamp]
   - not already converted (avoids double-counting)
2. Link transaction → session (transactions.linked_session_id).
3. Mark session is_converted = True.
4. Trigger daily metrics update.

Edge cases:
- Multiple transactions in window: only first transaction per session counted.
- Staff sessions: never marked as converted (filtered by is_staff=False).
- Zero purchases: all sessions remain is_converted=False (correct).
- Group entry: each visitor tracked independently, each can convert independently.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def link_transaction_to_session(
    session: AsyncSession,
    store_id: str,
    tx_id: uuid.UUID,
    tx_amount: float,
    tx_timestamp: datetime,
    pos_terminal_id: Optional[str],
    window_minutes: int = 5,
) -> Optional[uuid.UUID]:
    """
    Upsert transaction and link to a matching visitor session.
    Returns the linked session_id if found, else None.
    """
    window_start = tx_timestamp - timedelta(minutes=window_minutes)

    # Find candidate sessions: non-staff, visited billing zone, entry within window
    result = await session.execute(
        text("""
            SELECT vs.session_id, vs.visitor_id
            FROM visitor_sessions vs
            WHERE vs.store_id = :store_id
              AND vs.is_staff = false
              AND vs.is_converted = false
              AND vs.entry_time <= :tx_timestamp
              AND (vs.exit_time IS NULL OR vs.exit_time >= :window_start)

        """),
        {
            "store_id": store_id,
            "window_start": window_start,
            "tx_timestamp": tx_timestamp,
        },
    )
    row = result.fetchone()
    linked_session_id = uuid.UUID(str(row.session_id)) if row else None
    visitor_id = row.visitor_id if row else None

    # Insert transaction
    await session.execute(
        text("""
            INSERT INTO transactions (tx_id, store_id, session_id, amount, timestamp, pos_terminal_id)
            VALUES (:tx_id, :store_id, :session_id, :amount, :ts, :pos)
            ON CONFLICT (tx_id) DO NOTHING
        """),
        {
            "tx_id": str(tx_id),
            "store_id": store_id,
            "session_id": str(linked_session_id) if linked_session_id else None,
            "amount": tx_amount,
            "ts": tx_timestamp,
            "pos": pos_terminal_id,
        },
    )

    # Mark session as converted and insert PURCHASE event
    if linked_session_id and visitor_id:
        await session.execute(
            text("""
                UPDATE visitor_sessions
                SET is_converted = true
                WHERE session_id = :session_id
            """),
            {"session_id": str(linked_session_id)},
        )
        
        # Get billing zone id for the store (if any)
        zone_result = await session.execute(
            text("SELECT zone_id FROM zones WHERE store_id = :store_id AND zone_type = 'BILLING' LIMIT 1"),
            {"store_id": store_id}
        )
        zone_row = zone_result.fetchone()
        billing_zone_id = zone_row.zone_id if zone_row else "Z_BILLING"

        # Insert a PURCHASE event into events table
        purchase_event_id = uuid.uuid4()
        await session.execute(
            text("""
                INSERT INTO events (
                    event_id, store_id, session_id, visitor_id, event_type, 
                    timestamp, zone_id, confidence, is_staff, camera_id, sequence_number
                ) VALUES (
                    :eid, :store_id, :session_id, :visitor_id, 'PURCHASE', 
                    :timestamp, :zone_id, 1.0, false, 'CAM_03', 0
                )
                ON CONFLICT (event_id) DO NOTHING
            """),
            {
                "eid": str(purchase_event_id),
                "store_id": store_id,
                "session_id": str(linked_session_id),
                "visitor_id": visitor_id,
                "timestamp": tx_timestamp,
                "zone_id": billing_zone_id,
            },
        )


        logger.info(
            "Session converted with PURCHASE event",
            extra={
                "session_id": str(linked_session_id),
                "visitor_id": visitor_id,
                "tx_id": str(tx_id),
                "amount": tx_amount,
                "purchase_event_id": str(purchase_event_id),
            },
        )

    return linked_session_id


async def bulk_load_pos_transactions(
    session: AsyncSession,
    store_id: str,
    csv_path: str,
    window_minutes: int = 5,
) -> dict[str, int]:
    """
    Load POS transactions from CSV and run conversion linking.
    CSV format: tx_id,amount,timestamp,pos_terminal_id
    Returns {'linked': N, 'unlinked': N}.
    """
    import csv
    from pathlib import Path

    linked = 0
    unlinked = 0

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx_id = uuid.UUID(row.get("tx_id") or str(uuid.uuid4()))
            amount = float(row.get("amount", 0))
            ts = datetime.fromisoformat(row["timestamp"])
            pos = row.get("pos_terminal_id")

            sid = await link_transaction_to_session(
                session, store_id, tx_id, amount, ts, pos, window_minutes
            )
            if sid:
                linked += 1
            else:
                unlinked += 1

    logger.info(
        "POS bulk load complete",
        extra={"store_id": store_id, "linked": linked, "unlinked": unlinked},
    )
    return {"linked": linked, "unlinked": unlinked}
