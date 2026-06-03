# PROMPT: "Write unit tests for an EventGenerator class that emits structured retail CV events.
# Test: emit_entry returns ENTRY type event with correct visitor_id, UUID event_id assignment,
# session_seq increments per visitor, consistent visitor_id across events, different visitors get
# different IDs, deduplication suppresses repeat entry events, invalid event types return None,
# zone confidence penalty applied, reentry creates new session, queue_join includes queue_depth,
# all valid event types accepted, naive timestamps get UTC timezone."
#
# CHANGES MADE:
# - test_dedup_prevents_duplicate_events: AI assumed dedup was by event_id. Changed to test same-visitor
#   same-type same-timestamp dedup (the actual implementation deduplicates on visitor/type/time).
# - test_reentry_creates_new_session: AI generated generic REENTRY test. Extended to check new_session_id
#   in metadata (our specific implementation detail).
# - Removed test_emit_uses_store_and_camera_ids (trivial getter, low value).
"""Unit tests for Event Generator."""
import uuid
from datetime import datetime, timezone, timedelta

import pytest

from pipeline.event_generator import EventGenerator, VALID_EVENT_TYPES


def make_gen():
    return EventGenerator(store_id="STORE_BLR_002", camera_id="CAM_01")


class TestEventGenerator:

    def test_emit_entry_returns_event(self):
        gen = make_gen()
        ev = gen.emit_entry("VIS_001", datetime.now(timezone.utc))
        assert ev is not None
        assert ev.event_type == "ENTRY"
        assert ev.visitor_id == "VIS_001"

    def test_emit_assigns_uuid(self):
        gen = make_gen()
        ev = gen.emit_entry("VIS_001", datetime.now(timezone.utc))
        assert isinstance(ev.event_id, uuid.UUID)

    def test_sequence_increments(self):
        gen = make_gen()
        ts = datetime.now(timezone.utc)
        ev1 = gen.emit_entry("VIS_001", ts)
        ev2 = gen.emit_zone_enter("VIS_001", "ZONE_SKINCARE_01", ts + timedelta(seconds=5))
        assert ev2.metadata["session_seq"] > ev1.metadata["session_seq"]

    def test_session_id_consistent_per_visitor(self):
        gen = make_gen()
        ts = datetime.now(timezone.utc)
        ev1 = gen.emit_entry("VIS_001", ts)
        ev2 = gen.emit_zone_enter("VIS_001", "ZONE_SKINCARE_01", ts + timedelta(seconds=5))
        assert ev1.visitor_id == ev2.visitor_id  # Re-ID acts as session token

    def test_different_visitors_different_sessions(self):
        gen = make_gen()
        ts = datetime.now(timezone.utc)
        ev1 = gen.emit_entry("VIS_001", ts)
        ev2 = gen.emit_entry("VIS_002", ts)
        assert ev1.visitor_id != ev2.visitor_id

    def test_dedup_prevents_duplicate_events(self):
        gen = make_gen()
        ts = datetime.now(timezone.utc)
        ev1 = gen.emit_entry("VIS_001", ts)
        ev2 = gen.emit_entry("VIS_001", ts)  # Same visitor, type, timestamp
        assert ev1 is not None
        assert ev2 is None  # Duplicate suppressed

    def test_invalid_event_type_returns_none(self):
        gen = make_gen()
        ev = gen.emit("VIS_001", "INVALID_TYPE", datetime.now(timezone.utc))
        assert ev is None

    def test_confidence_reduced_for_zone_events(self):
        gen = make_gen()
        ts = datetime.now(timezone.utc)
        ev = gen.emit_zone_enter("VIS_001", "ZONE_01", ts, detection_confidence=1.0)
        assert ev.confidence < 1.0  # Zone confidence penalty applied

    def test_reentry_creates_new_session(self):
        gen = make_gen()
        ts = datetime.now(timezone.utc)
        ev1 = gen.emit_entry("VIS_001", ts)
        ev_re = gen.emit_reentry("VIS_001", ts + timedelta(minutes=15))
        assert ev1 is not None
        assert ev_re is not None
        assert ev_re.event_type == "REENTRY"
        # New session is managed internally, but visitor_id is the same.
        assert ev1.visitor_id == ev_re.visitor_id
        # The new session ID generated internally is stored in metadata
        assert ev_re.metadata.get("new_session_id") is not None

    def test_queue_join_includes_queue_depth(self):
        gen = make_gen()
        ts = datetime.now(timezone.utc)
        ev = gen.emit_queue_join("VIS_001", "ZONE_BILLING_01", ts, queue_depth=5)
        assert ev is not None
        assert ev.metadata.get("queue_depth") == 5

    def test_all_valid_event_types_accepted(self):
        gen = make_gen()
        ts = datetime.now(timezone.utc)
        for i, etype in enumerate(VALID_EVENT_TYPES):
            ev = gen.emit(
                f"VIS_{i:03d}",
                etype,
                ts + timedelta(seconds=i),
            )
            assert ev is not None, f"Event type {etype} should be valid"

    def test_timestamp_gets_utc_timezone(self):
        gen = make_gen()
        naive_ts = datetime(2026, 5, 30, 10, 0, 0)  # no tzinfo
        ev = gen.emit_entry("VIS_001", naive_ts)
        assert ev is not None
        assert ev.timestamp.tzinfo is not None
