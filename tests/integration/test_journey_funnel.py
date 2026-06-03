# PROMPT: "Write integration tests for a retail conversion funnel API (/stores/{id}/funnel and /metrics).
# The funnel must guarantee Purchase <= Billing <= Zone Engagement <= Entry mathematically.
# Test a complete visitor journey step-by-step: ENTRY only → then add ZONE_ENTER → then BILLING_QUEUE_JOIN
# → then POS transaction triggers PURCHASE. After each step verify funnel counts are correct and hierarchy
# invariant holds. Also test: cross-camera events for same visitor map to single session_id, metrics
# unique_visitors increments exactly 1 after ingesting 1 new ENTRY event."
#
# CHANGES MADE:
# - Step D (purchase): AI initially used POST /events/ingest with a PURCHASE event. Changed to call
#   link_transaction_to_session() directly — because in our architecture, purchases are detected via POS
#   correlation, not from the CV pipeline directly. This is a key design distinction.
# - Added 'ON CONFLICT DO NOTHING' to zone insert SQL (AI missed this, causing test failures on retry).
# - test_visitor_preserved_across_cameras: AI tested visitor_id equality. Extended to verify exact 1 session_id
#   in DB (tests the deterministic UUID5 keying implementation specifically).
import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient

from app.models.db_models import Zone, Store
from sqlalchemy import text


@pytest.mark.asyncio
class TestJourneyFunnel:

    async def test_funnel_strict_hierarchy(self, client: AsyncClient, db_session):
        # 1. Setup Store and Billing Zone
        store_id = "STORE_TEST_FUNNEL"
        
        await db_session.execute(
            text("INSERT INTO stores (store_id, name, timezone) VALUES (:store_id, :name, :tz) ON CONFLICT DO NOTHING"),
            {"store_id": store_id, "name": "Funnel Test Store", "tz": "Asia/Kolkata"}
        )
        await db_session.execute(
            text("""
                INSERT INTO zones (zone_id, store_id, name, zone_type, polygon_json, priority) 
                VALUES ('ZONE_BILL_TEST', :store_id, 'Billing Zone Test', 'BILLING', '[[0,0],[10,10]]', 1)
                ON CONFLICT DO NOTHING
            """),
            {"store_id": store_id}
        )
        await db_session.commit()

        # Define visitor
        vid = "VIS_FUNNEL_TEST_01"
        ts = datetime.now(timezone.utc)
        date_str = ts.date().isoformat()

        # Step A: Ingest ENTRY event (Entry Count should be 1, others 0)
        e1 = str(uuid.uuid4())
        resp = await client.post("/events/ingest", json={
            "events": [{
                "event_id": e1,
                "store_id": store_id,
                "camera_id": "CAM_01",
                "visitor_id": vid,
                "event_type": "ENTRY",
                "timestamp": ts.isoformat(),
            }]
        })
        assert resp.status_code == 200

        # Query Funnel
        resp = await client.get(f"/stores/{store_id}/funnel?date={date_str}")
        assert resp.status_code == 200
        funnel = {s["stage"]: s["count"] for s in resp.json()["stages"]}
        assert funnel["ENTRY"] == 1
        assert funnel["ZONE_ENGAGEMENT"] == 0
        assert funnel["BILLING_ZONE_REACHED"] == 0
        assert funnel["CONVERTED"] == 0

        # Step B: Ingest ZONE_ENTER event (Engagement Count should be 1, others 0)
        e2 = str(uuid.uuid4())
        resp = await client.post("/events/ingest", json={
            "events": [{
                "event_id": e2,
                "store_id": store_id,
                "camera_id": "CAM_02",
                "visitor_id": vid,
                "event_type": "ZONE_ENTER",
                "timestamp": ts.isoformat(),
                "zone_id": "ZONE_BILL_TEST" # entered zone
            }]
        })
        assert resp.status_code == 200

        # Query Funnel
        resp = await client.get(f"/stores/{store_id}/funnel?date={date_str}")
        assert resp.status_code == 200
        funnel = {s["stage"]: s["count"] for s in resp.json()["stages"]}
        assert funnel["ENTRY"] == 1
        assert funnel["ZONE_ENGAGEMENT"] == 1
        assert funnel["BILLING_ZONE_REACHED"] == 0
        assert funnel["CONVERTED"] == 0

        # Step C: Ingest BILLING_QUEUE_JOIN event
        e3 = str(uuid.uuid4())
        resp = await client.post("/events/ingest", json={
            "events": [{
                "event_id": e3,
                "store_id": store_id,
                "camera_id": "CAM_03",
                "visitor_id": vid,
                "event_type": "BILLING_QUEUE_JOIN",
                "timestamp": ts.isoformat(),
                "zone_id": "ZONE_BILL_TEST"
            }]
        })
        assert resp.status_code == 200

        # Query Funnel
        resp = await client.get(f"/stores/{store_id}/funnel?date={date_str}")
        assert resp.status_code == 200
        funnel = {s["stage"]: s["count"] for s in resp.json()["stages"]}
        assert funnel["ENTRY"] == 1
        assert funnel["ZONE_ENGAGEMENT"] == 1
        assert funnel["BILLING_ZONE_REACHED"] == 1
        assert funnel["CONVERTED"] == 0

        # Step D: Ingest transaction (marks conversion and generates PURCHASE event)
        tx_id = str(uuid.uuid4())
        resp = await client.post("/events/ingest", json={
            "events": [] # just to verify we can also run transaction linking separately via DB session
        })
        
        # Link transaction directly using the API if available or mock POS conversion call
        from app.services.conversion import link_transaction_to_session
        linked_sid = await link_transaction_to_session(
            db_session, store_id, uuid.UUID(tx_id), 1500.0, ts, "TERM_01"
        )
        assert linked_sid is not None
        await db_session.commit()

        # Query Funnel again - should be fully converted!
        resp = await client.get(f"/stores/{store_id}/funnel?date={date_str}")
        assert resp.status_code == 200
        funnel = {s["stage"]: s["count"] for s in resp.json()["stages"]}
        assert funnel["ENTRY"] == 1
        assert funnel["ZONE_ENGAGEMENT"] == 1
        assert funnel["BILLING_ZONE_REACHED"] == 1
        assert funnel["CONVERTED"] == 1

        # Enforce Purchase <= Billing <= Engagement <= Entry
        assert funnel["CONVERTED"] <= funnel["BILLING_ZONE_REACHED"] <= funnel["ZONE_ENGAGEMENT"] <= funnel["ENTRY"]

    async def test_visitor_preserved_across_cameras(self, client: AsyncClient, db_session):
        # Verify that session_id generation is deterministic per visitor/date, linking cameras CAM_01/02/03
        store_id = "STORE_TEST_REID"
        vid = "VIS_CROSS_CAM_TEST"
        ts = datetime.now(timezone.utc)
        
        e1 = str(uuid.uuid4())
        resp1 = await client.post("/events/ingest", json={
            "events": [{
                "event_id": e1,
                "store_id": store_id,
                "camera_id": "CAM_01", # entrance
                "visitor_id": vid,
                "event_type": "ENTRY",
                "timestamp": ts.isoformat(),
            }]
        })
        assert resp1.status_code == 200

        e2 = str(uuid.uuid4())
        resp2 = await client.post("/events/ingest", json={
            "events": [{
                "event_id": e2,
                "store_id": store_id,
                "camera_id": "CAM_02", # floor
                "visitor_id": vid,
                "event_type": "ZONE_ENTER",
                "timestamp": ts.isoformat(),
            }]
        })
        assert resp2.status_code == 200

        # Query events from database to verify they mapped to the exact same session_id
        res = await db_session.execute(
            text("SELECT DISTINCT session_id FROM events WHERE visitor_id = :vid AND store_id = :store_id"),
            {"vid": vid, "store_id": store_id}
        )
        session_ids = [str(r.session_id) for r in res.fetchall()]
        assert len(session_ids) == 1 # exactly one linked session

    async def test_metrics_update_after_ingestion(self, client: AsyncClient, db_session):
        store_id = "STORE_TEST_METRICS"
        ts = datetime.now(timezone.utc)
        date_str = ts.date().isoformat()

        # Get initial metrics (should be empty/fallback 0s since we don't have seed data for this store)
        resp = await client.get(f"/stores/{store_id}/metrics?date={date_str}")
        assert resp.status_code == 200
        initial_visitors = resp.json()["unique_visitors"]

        # Ingest new visitor
        resp = await client.post("/events/ingest", json={
            "events": [{
                "event_id": str(uuid.uuid4()),
                "store_id": store_id,
                "camera_id": "CAM_01",
                "visitor_id": "VIS_METRICS_NEW",
                "event_type": "ENTRY",
                "timestamp": ts.isoformat(),
            }]
        })
        assert resp.status_code == 200

        # Query metrics again - should have updated unique visitors count
        resp = await client.get(f"/stores/{store_id}/metrics?date={date_str}")
        assert resp.status_code == 200
        new_visitors = resp.json()["unique_visitors"]
        assert new_visitors == initial_visitors + 1
