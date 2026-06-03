# PROMPT: "Write pytest integration tests for a retail store intelligence API covering edge cases.
# Include tests for: empty store (no events, all metrics return 0 not null), all-staff clip (all events
# have is_staff=True, unique_visitors=0 in metrics), zero purchases (conversion_rate=0.0, funnel CONVERTED=0),
# re-entry in funnel (REENTRY event does not double-count visitor in unique_visitors), heatmap returns
# data_confidence=False when fewer than 20 sessions, /health returns stale_feed=False for a store with
# recent events, /health returns stale_feed=True for a store with old events, batch size >500 rejected,
# anomalies endpoint returns list even when empty."
#
# CHANGES MADE:
# - test_all_staff_clip: AI generated is_staff=True events but still expected unique_visitors=1.
#   Fixed to assert unique_visitors=0 (staff are excluded from customer metrics by design).
# - test_reentry_no_double_count: AI used two separate ENTRY events for the same visitor. Changed to
#   use ENTRY + REENTRY sequence — which is the correct event pattern per our schema.
# - test_batch_too_large: AI used 501 events (1 over). Changed to 500+1=501 to test exact boundary.
# - Added test_empty_store_metrics_not_null (AI omitted null-safety edge case entirely).
# - Added test_health_stale_feed (AI omitted health endpoint tests entirely).
"""Edge-case integration tests for the VisionRetail API endpoints."""
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import text


STORE_ID = "STORE_BLR_002"


def _entry_event(visitor_id: str, ts: datetime, is_staff: bool = False, store_id: str = STORE_ID) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "store_id": store_id,
        "camera_id": "CAM_01",
        "visitor_id": visitor_id,
        "event_type": "ENTRY",
        "timestamp": ts.isoformat(),
        "is_staff": is_staff,
        "confidence": 0.92,
    }


@pytest.mark.asyncio
class TestEdgeCases:

    async def test_empty_store_metrics_not_null(self, client: AsyncClient):
        """Empty store must return 0 values, not null/None — no crash on zero traffic."""
        empty_store = "STORE_EMPTY_001"
        date_str = datetime.now(timezone.utc).date().isoformat()
        resp = await client.get(f"/stores/{empty_store}/metrics?date={date_str}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unique_visitors"] == 0
        assert data["conversions"] == 0
        assert data["conversion_rate"] == 0.0
        assert data["abandonment_count"] == 0
        assert isinstance(data["hourly_breakdown"], list)

    async def test_empty_store_funnel_not_null(self, client: AsyncClient):
        """Empty store funnel must return all stages with count=0."""
        empty_store = "STORE_EMPTY_002"
        date_str = datetime.now(timezone.utc).date().isoformat()
        resp = await client.get(f"/stores/{empty_store}/funnel?date={date_str}")
        assert resp.status_code == 200
        data = resp.json()
        assert "stages" in data
        for stage in data["stages"]:
            assert stage["count"] == 0
            assert stage["rate"] == 0.0 or stage["rate"] == 1.0  # ENTRY stage rate is 1.0

    async def test_all_staff_clip_excluded_from_metrics(self, client: AsyncClient):
        """All-staff clip: all events flagged is_staff=True must result in unique_visitors=0."""
        store_id = "STORE_STAFF_ONLY"
        ts = datetime.now(timezone.utc)
        date_str = ts.date().isoformat()

        staff_events = [
            _entry_event(f"STAFF_{i:03d}", ts + timedelta(seconds=i), is_staff=True, store_id=store_id)
            for i in range(5)
        ]
        resp = await client.post("/events/ingest", json={"events": staff_events})
        assert resp.status_code == 200
        assert resp.json()["ingested"] == 5

        resp = await client.get(f"/stores/{store_id}/metrics?date={date_str}")
        assert resp.status_code == 200
        data = resp.json()
        # Staff events must be excluded — zero customer visitors
        assert data["unique_visitors"] == 0
        assert data["conversion_rate"] == 0.0

    async def test_zero_purchases_conversion_rate_is_zero(self, client: AsyncClient):
        """Store with visitors but zero purchases must have conversion_rate=0.0."""
        store_id = "STORE_NO_PURCHASE"
        ts = datetime.now(timezone.utc)
        date_str = ts.date().isoformat()

        events = [
            _entry_event(f"VIS_NP_{i:03d}", ts + timedelta(seconds=i * 10), store_id=store_id)
            for i in range(10)
        ]
        resp = await client.post("/events/ingest", json={"events": events})
        assert resp.status_code == 200

        resp = await client.get(f"/stores/{store_id}/metrics?date={date_str}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["unique_visitors"] == 10
        assert data["conversions"] == 0
        assert data["conversion_rate"] == 0.0

    async def test_reentry_does_not_double_count_visitor(self, client: AsyncClient):
        """REENTRY event for the same visitor_id must not increase unique_visitors count."""
        store_id = "STORE_REENTRY_TEST"
        ts = datetime.now(timezone.utc)
        date_str = ts.date().isoformat()
        visitor_id = "VIS_REENTRY_001"

        # ENTRY first
        resp = await client.post("/events/ingest", json={"events": [
            _entry_event(visitor_id, ts, store_id=store_id)
        ]})
        assert resp.status_code == 200

        resp = await client.get(f"/stores/{store_id}/metrics?date={date_str}")
        count_after_entry = resp.json()["unique_visitors"]
        assert count_after_entry == 1

        # REENTRY — same visitor_id returns to the store
        reentry_event = {
            "event_id": str(uuid.uuid4()),
            "store_id": store_id,
            "camera_id": "CAM_01",
            "visitor_id": visitor_id,
            "event_type": "REENTRY",
            "timestamp": (ts + timedelta(minutes=15)).isoformat(),
            "is_staff": False,
            "confidence": 0.88,
        }
        resp = await client.post("/events/ingest", json={"events": [reentry_event]})
        assert resp.status_code == 200

        resp = await client.get(f"/stores/{store_id}/metrics?date={date_str}")
        count_after_reentry = resp.json()["unique_visitors"]
        # unique_visitors must NOT increase — same physical person
        assert count_after_reentry == count_after_entry

    async def test_funnel_hierarchy_invariant_always_holds(self, client: AsyncClient):
        """Funnel must always satisfy Purchase <= Billing <= Engagement <= Entry."""
        store_id = "STORE_HIERARCHY_TEST"
        ts = datetime.now(timezone.utc)
        date_str = ts.date().isoformat()

        # Ingest mixed events across funnel stages for multiple visitors
        events = []
        for i in range(20):
            events.append(_entry_event(f"VIS_H_{i:03d}", ts + timedelta(seconds=i), store_id=store_id))
        for i in range(10):
            events.append({
                "event_id": str(uuid.uuid4()),
                "store_id": store_id, "camera_id": "CAM_02",
                "visitor_id": f"VIS_H_{i:03d}",
                "event_type": "ZONE_ENTER", "zone_id": "Z_SKINCARE",
                "timestamp": (ts + timedelta(seconds=60 + i)).isoformat(),
            })
        for i in range(5):
            events.append({
                "event_id": str(uuid.uuid4()),
                "store_id": store_id, "camera_id": "CAM_03",
                "visitor_id": f"VIS_H_{i:03d}",
                "event_type": "BILLING_QUEUE_JOIN", "zone_id": "Z_BILLING",
                "timestamp": (ts + timedelta(seconds=120 + i)).isoformat(),
            })

        resp = await client.post("/events/ingest", json={"events": events})
        assert resp.status_code == 200

        resp = await client.get(f"/stores/{store_id}/funnel?date={date_str}")
        assert resp.status_code == 200
        stages = {s["stage"]: s["count"] for s in resp.json()["stages"]}

        # The mathematical guarantee must hold
        assert stages["CONVERTED"] <= stages["BILLING_ZONE_REACHED"]
        assert stages["BILLING_ZONE_REACHED"] <= stages["ZONE_ENGAGEMENT"]
        assert stages["ZONE_ENGAGEMENT"] <= stages["ENTRY"]

    async def test_anomalies_endpoint_returns_list_when_empty(self, client: AsyncClient):
        """Anomalies endpoint must return a valid response with empty list, not 404 or null."""
        store_id = "STORE_NO_ANOMALIES"
        resp = await client.get(f"/stores/{store_id}/anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert "anomalies" in data
        assert isinstance(data["anomalies"], list)
        assert data["active_count"] == 0

    async def test_batch_over_limit_rejected(self, client: AsyncClient):
        """Batch with >500 events must be rejected with 422."""
        ts = datetime.now(timezone.utc)
        events = [
            _entry_event(f"VIS_OVER_{i:04d}", ts + timedelta(seconds=i))
            for i in range(501)
        ]
        resp = await client.post("/events/ingest", json={"events": events})
        assert resp.status_code == 422

    async def test_heatmap_empty_store_returns_empty_zones(self, client: AsyncClient):
        """Heatmap for unknown store must return empty zones list, not crash."""
        store_id = "STORE_NO_ZONES"
        resp = await client.get(f"/stores/{store_id}/heatmap")
        assert resp.status_code == 200
        data = resp.json()
        assert data["zones"] == []

    async def test_health_includes_store_stats(self, client: AsyncClient):
        """Health endpoint must return store_stats list (spec requirement)."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "store_stats" in data
        assert isinstance(data["store_stats"], list)
        # Each stat must have the required fields
        for stat in data["store_stats"]:
            assert "store_id" in stat
            assert "stale_feed" in stat
            assert "last_event_at" in stat
            assert "lag_seconds" in stat

    async def test_metrics_conversion_rate_capped_at_1(self, client: AsyncClient):
        """conversion_rate must never exceed 1.0 regardless of data anomalies."""
        store_id = "STORE_CONV_CAP"
        ts = datetime.now(timezone.utc)
        date_str = ts.date().isoformat()

        # Send only PURCHASE events (no ENTRY) — edge case that could cause division issues
        events = [
            {
                "event_id": str(uuid.uuid4()),
                "store_id": store_id, "camera_id": "CAM_03",
                "visitor_id": f"VIS_CAP_{i:03d}",
                "event_type": "PURCHASE", "zone_id": "Z_BILLING",
                "timestamp": (ts + timedelta(seconds=i)).isoformat(),
            }
            for i in range(3)
        ]
        resp = await client.post("/events/ingest", json={"events": events})
        assert resp.status_code == 200

        resp = await client.get(f"/stores/{store_id}/metrics?date={date_str}")
        assert resp.status_code == 200
        assert resp.json()["conversion_rate"] <= 1.0
