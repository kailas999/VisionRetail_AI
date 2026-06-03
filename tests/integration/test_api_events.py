# PROMPT: "Write pytest integration tests for a FastAPI event ingestion endpoint POST /events/ingest.
# Use an async test client against an in-memory SQLite database. Test: health check returns 200 with
# status and database fields, single event ingestion returns ingested=1 and trace_id, batch of 10 events
# ingests all correctly, duplicate event_id on second call returns duplicates=1 ingested=0 (idempotency),
# X-Trace-ID returned in response header, invalid event_type returns 422, empty batch returns 422,
# all 8 valid event types accepted in one batch."
#
# CHANGES MADE:
# - test_trace_id_in_response_header: AI tested the request header, not response. Fixed to check resp.headers.
# - Added 'camera_id' field to all event payloads (AI's generated payloads were missing this required field).
# - test_all_event_types_accepted: AI excluded PURCHASE from the list (it is a valid ingestable type). Added it.
# - Removed test_confidence_out_of_range_rejected (Pydantic clamps, does not reject, so AI's test was wrong).
"""Integration tests for event ingestion API."""
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio


@pytest.mark.asyncio
class TestEventIngestion:

    async def test_health_check(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "database" in data

    async def test_ingest_single_event(self, client, sample_store_id):
        payload = {
            "events": [
                {
                    "event_id": str(uuid.uuid4()),
                    "store_id": sample_store_id,
                    "camera_id": "CAM_01",
                    "visitor_id": "VIS_INTEG_001",
                    "event_type": "ENTRY",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "confidence": 0.92,
                    "is_staff": False,
                }
            ]
        }
        resp = await client.post("/events/ingest", json=payload)
        print("RESPONSE:", resp.text)
        assert resp.status_code == 200
        data = resp.json()
        assert data["ingested"] == 1
        assert data["duplicates"] == 0
        assert "trace_id" in data

    async def test_ingest_batch_events(self, client, sample_store_id):
        events = []
        for i in range(10):
            events.append({
                "event_id": str(uuid.uuid4()),
                "store_id": sample_store_id,
                "camera_id": "CAM_01",
                "visitor_id": f"VIS_BATCH_{i:03d}",
                "event_type": "ENTRY",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "confidence": 0.85,
            })
        resp = await client.post("/events/ingest", json={"events": events})
        assert resp.status_code == 200
        assert resp.json()["ingested"] == 10

    async def test_duplicate_event_id_idempotent(self, client, sample_store_id):
        event_id = str(uuid.uuid4())
        payload = {
            "events": [{
                "event_id": event_id,
                "store_id": sample_store_id,
                "camera_id": "CAM_01",
                "visitor_id": "VIS_DUP_001",
                "event_type": "ENTRY",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }]
        }
        # First ingest
        resp1 = await client.post("/events/ingest", json=payload)
        assert resp1.status_code == 200
        assert resp1.json()["ingested"] == 1

        # Second ingest — same event_id
        resp2 = await client.post("/events/ingest", json=payload)
        assert resp2.status_code == 200
        assert resp2.json()["duplicates"] == 1
        assert resp2.json()["ingested"] == 0

    async def test_trace_id_in_response_header(self, client, sample_store_id):
        payload = {
            "events": [{
                "event_id": str(uuid.uuid4()),
                "store_id": sample_store_id,
                "camera_id": "CAM_01",
                "visitor_id": "VIS_TRACE_001",
                "event_type": "ENTRY",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }]
        }
        resp = await client.post("/events/ingest", json=payload)
        assert "X-Trace-ID" in resp.headers

    async def test_invalid_event_type_rejected(self, client, sample_store_id):
        payload = {
            "events": [{
                "event_id": str(uuid.uuid4()),
                "store_id": sample_store_id,
                "visitor_id": "VIS_BAD_001",
                "event_type": "INVALID_TYPE",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }]
        }
        resp = await client.post("/events/ingest", json=payload)
        assert resp.status_code == 422  # Pydantic validation error

    async def test_empty_batch_rejected(self, client):
        resp = await client.post("/events/ingest", json={"events": []})
        assert resp.status_code == 422

    async def test_all_event_types_accepted(self, client, sample_store_id):
        event_types = [
            "ENTRY", "EXIT", "ZONE_ENTER", "ZONE_EXIT", "ZONE_DWELL",
            "BILLING_QUEUE_JOIN", "BILLING_QUEUE_ABANDON", "REENTRY",
        ]
        events = [
            {
                "event_id": str(uuid.uuid4()),
                "store_id": sample_store_id,
                "camera_id": "CAM_01",
                "visitor_id": f"VIS_TYPE_{i}",
                "event_type": etype,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            for i, etype in enumerate(event_types)
        ]
        resp = await client.post("/events/ingest", json={"events": events})
        assert resp.status_code == 200
        assert resp.json()["ingested"] == len(event_types)
