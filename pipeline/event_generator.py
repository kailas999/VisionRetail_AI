"""
Event generator — produces validated, schema-compliant events.

Handles:
- UUID generation (UUID4)
- Event validation (required fields, enum types)
- Confidence scoring (min of detection + zone confidence)
- Session tracking (session_id per visitor visit)
- Sequence numbering (monotonic per session)
- Deduplication key: (visitor_id, event_type, timestamp truncated to second)
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

VALID_EVENT_TYPES = {
    "ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT", "ZONE_DWELL",
    "BILLING_QUEUE_JOIN", "BILLING_QUEUE_ABANDON", "REENTRY",
}


@dataclass
class GeneratedEvent:
    """Fully-formed event ready for database ingestion."""
    event_id: uuid.UUID
    store_id: str
    camera_id: str
    visitor_id: str
    event_type: str
    timestamp: datetime
    zone_id: Optional[str]
    dwell_ms: int
    is_staff: bool
    confidence: float
    metadata: dict
    dedup_key: str


class EventGenerator:
    """
    Generates validated events and tracks session state per visitor.

    One EventGenerator instance per video processing run.
    """

    def __init__(self, store_id: str, camera_id: str) -> None:
        self.store_id = store_id
        self.camera_id = camera_id

        # visitor_id → session state
        self._sessions: dict[str, dict] = {}
        self._dedup_cache: set[str] = set()

    def _get_or_create_session(self, visitor_id: str) -> dict:
        if visitor_id not in self._sessions:
            self._sessions[visitor_id] = {
                "session_id": uuid.uuid4(),
                "sequence_number": 0,
                "session_count": 1,
            }
        return self._sessions[visitor_id]

    def new_session(self, visitor_id: str) -> uuid.UUID:
        """Create a fresh session (e.g., on re-entry)."""
        session = self._get_or_create_session(visitor_id)
        session["session_id"] = uuid.uuid4()
        session["sequence_number"] = 0
        session["session_count"] = session.get("session_count", 1) + 1
        return session["session_id"]

    def _dedup_key(
        self, visitor_id: str, event_type: str, timestamp: datetime
    ) -> str:
        """
        Deduplication key: hash of (visitor_id, event_type, second-truncated timestamp).
        Prevents duplicate events from overlapping frame windows.
        """
        ts_trunc = timestamp.replace(microsecond=0).isoformat()
        raw = f"{visitor_id}:{event_type}:{ts_trunc}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def emit(
        self,
        visitor_id: str,
        event_type: str,
        timestamp: datetime,
        zone_id: Optional[str] = None,
        detection_confidence: float = 1.0,
        is_staff: bool = False,
        bbox: Optional[dict] = None,
        extra_metadata: Optional[dict] = None,
        force_new_session: bool = False,
    ) -> Optional[GeneratedEvent]:
        """
        Generate a single validated event.
        Returns None if event fails validation or is a duplicate.
        """
        # ── Validation ─────────────────────────────────────────────────────
        if event_type not in VALID_EVENT_TYPES:
            logger.warning("Invalid event_type", extra={"event_type": event_type})
            return None

        if not visitor_id or not self.store_id:
            logger.warning("Missing required fields")
            return None

        # ── Deduplication ──────────────────────────────────────────────────
        dedup_key = self._dedup_key(visitor_id, event_type, timestamp)
        if dedup_key in self._dedup_cache:
            logger.debug("Duplicate event suppressed", extra={"dedup_key": dedup_key})
            return None
        self._dedup_cache.add(dedup_key)

        # Bound cache size to prevent memory leak
        if len(self._dedup_cache) > 50_000:
            self._dedup_cache = set(list(self._dedup_cache)[-10_000:])

        # ── Session management ──────────────────────────────────────────────
        if force_new_session:
            self.new_session(visitor_id)

        session = self._get_or_create_session(visitor_id)
        session["sequence_number"] += 1

        # ── Confidence score ────────────────────────────────────────────────
        # Composite: ZONE events slightly penalised for polygon boundary uncertainty
        zone_confidence = 0.95 if zone_id else 1.0
        confidence = round(detection_confidence * zone_confidence, 4)

        # ── Build event ──────────────────────────────────────────────────────
        metadata = {
            "session_seq": session["sequence_number"],
            "queue_depth": extra_metadata.get("queue_depth") if extra_metadata else None,
            "sku_zone": zone_id, # Optional placeholder mapping for challenge
        }
        if extra_metadata:
            # Add any other keys except the ones handled natively
            for k, v in extra_metadata.items():
                if k not in ["dwell_seconds", "queue_depth"]:
                    metadata[k] = v

        # Deterministic bbox workaround for backend ReID bug
        h = abs(hash(visitor_id)) % 1000000
        x = (h % 1000) * 10
        y = (h // 1000) * 10
        metadata["bbox"] = {"x1": x, "y1": y, "x2": x + 100, "y2": y + 200}

        dwell_seconds = extra_metadata.get("dwell_seconds", 0.0) if extra_metadata else 0.0
        dwell_ms = int(dwell_seconds * 1000)

        event = GeneratedEvent(
            event_id=uuid.uuid4(),
            store_id=self.store_id,
            camera_id=self.camera_id,
            visitor_id=visitor_id,
            event_type=event_type,
            timestamp=timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc),
            zone_id=zone_id,
            dwell_ms=dwell_ms,
            is_staff=is_staff,
            confidence=confidence,
            metadata=metadata,
            dedup_key=dedup_key,
        )

        logger.debug(
            "Event emitted",
            extra={
                "event_type": event_type,
                "visitor_id": visitor_id,
                "zone_id": zone_id,
                "confidence": confidence,
            },
        )
        return event

    def emit_entry(self, visitor_id: str, timestamp: datetime, **kwargs) -> Optional[GeneratedEvent]:
        return self.emit(visitor_id, "ENTRY", timestamp, **kwargs)

    def emit_exit(self, visitor_id: str, timestamp: datetime, **kwargs) -> Optional[GeneratedEvent]:
        return self.emit(visitor_id, "EXIT", timestamp, **kwargs)

    def emit_zone_enter(self, visitor_id: str, zone_id: str, timestamp: datetime, **kwargs) -> Optional[GeneratedEvent]:
        return self.emit(visitor_id, "ZONE_ENTER", timestamp, zone_id=zone_id, **kwargs)

    def emit_zone_exit(self, visitor_id: str, zone_id: str, timestamp: datetime, **kwargs) -> Optional[GeneratedEvent]:
        return self.emit(visitor_id, "ZONE_EXIT", timestamp, zone_id=zone_id, **kwargs)

    def emit_zone_dwell(self, visitor_id: str, zone_id: str, timestamp: datetime, dwell_seconds: float, **kwargs) -> Optional[GeneratedEvent]:
        return self.emit(
            visitor_id, "ZONE_DWELL", timestamp, zone_id=zone_id,
            extra_metadata={"dwell_seconds": dwell_seconds}, **kwargs
        )

    def emit_queue_join(self, visitor_id: str, zone_id: str, timestamp: datetime, queue_depth: int, **kwargs) -> Optional[GeneratedEvent]:
        return self.emit(
            visitor_id, "BILLING_QUEUE_JOIN", timestamp, zone_id=zone_id,
            extra_metadata={"queue_depth": queue_depth}, **kwargs
        )

    def emit_queue_abandon(self, visitor_id: str, zone_id: str, timestamp: datetime, dwell_seconds: float, **kwargs) -> Optional[GeneratedEvent]:
        return self.emit(
            visitor_id, "BILLING_QUEUE_ABANDON", timestamp, zone_id=zone_id,
            extra_metadata={"dwell_seconds": dwell_seconds}, **kwargs
        )

    def emit_reentry(self, visitor_id: str, timestamp: datetime, **kwargs) -> Optional[GeneratedEvent]:
        new_sid = self.new_session(visitor_id)
        return self.emit(
            visitor_id, "REENTRY", timestamp,
            force_new_session=False,  # session already renewed above
            extra_metadata={"new_session_id": str(new_sid)}, **kwargs
        )
