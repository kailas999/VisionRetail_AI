# -*- coding: utf-8 -*-
"""
seed_data.py -- Populate VisionRetail DB with realistic demo data.
Run from backend/ directory:
    python seed_data.py
"""
import asyncio
import os
import sys
import uuid
import random
import json
from datetime import datetime, date, timedelta, timezone
from app.services.aggregation import update_hourly_metrics, update_daily_metrics
from app.services.anomaly import run_anomaly_detection

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

settings = get_settings()
DATABASE_URL = settings.database_url
print(f"Seeding -> {DATABASE_URL}")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

STORE_ID = "STORE_BLR_002"
TODAY = date.today()
NOW = datetime.now(timezone.utc)

ZONES = [
    {"zone_id": "Z_ENTRANCE",  "name": "Entrance",  "zone_type": "ENTRY",   "polygon": [[0,0],[100,0],[100,80],[0,80]],        "priority": 10},
    {"zone_id": "Z_SKINCARE",  "name": "Skincare",  "zone_type": "DISPLAY", "polygon": [[110,0],[250,0],[250,120],[110,120]],   "priority": 5},
    {"zone_id": "Z_FRAGRANCE", "name": "Fragrance", "zone_type": "DISPLAY", "polygon": [[260,0],[380,0],[380,120],[260,120]],   "priority": 5},
    {"zone_id": "Z_MAKEUP",    "name": "Makeup",    "zone_type": "DISPLAY", "polygon": [[110,130],[250,130],[250,260],[110,260]],"priority": 5},
    {"zone_id": "Z_HAIRCARE",  "name": "Haircare",  "zone_type": "AISLE",   "polygon": [[260,130],[380,130],[380,260],[260,260]],"priority": 3},
    {"zone_id": "Z_WELLNESS",  "name": "Wellness",  "zone_type": "AISLE",   "polygon": [[390,0],[510,0],[510,130],[390,130]],   "priority": 3},
    {"zone_id": "Z_GIFTING",   "name": "Gifting",   "zone_type": "DISPLAY", "polygon": [[390,140],[510,140],[510,260],[390,260]],"priority": 4},
    {"zone_id": "Z_BILLING",   "name": "Billing",   "zone_type": "BILLING", "polygon": [[520,0],[620,0],[620,200],[520,200]],   "priority": 8},
]

HOURLY_PATTERN = [
    (10, 42,  7,  180, 2, 1),
    (11, 68, 14,  210, 3, 2),
    (12, 95, 22,  280, 5, 3),
    (13, 112,28,  310, 7, 4),
    (14, 138,35,  340, 9, 6),
    (15, 125,30,  320, 8, 5),
    (16, 108,25,  295, 6, 4),
    (17, 118,28,  315, 7, 4),
    (18, 132,33,  330, 8, 5),
    (19, 98, 22,  270, 5, 3),
    (20, 72, 15,  220, 4, 2),
    (21, 45,  9,  190, 2, 1),
    (22, 30,  5,  150, 1, 0),
    (23, 15,  2,  120, 0, 0),
]

DWELL_BY_ZONE = {
    "Z_ENTRANCE":  42,
    "Z_SKINCARE":  412,
    "Z_FRAGRANCE": 287,
    "Z_MAKEUP":    521,
    "Z_HAIRCARE":  198,
    "Z_WELLNESS":  154,
    "Z_GIFTING":   233,
    "Z_BILLING":   96,
}

VISITOR_COUNTS_BY_ZONE = {
    "Z_ENTRANCE":  1153,
    "Z_SKINCARE":  386,
    "Z_FRAGRANCE": 244,
    "Z_MAKEUP":    498,
    "Z_HAIRCARE":  172,
    "Z_WELLNESS":  118,
    "Z_GIFTING":   209,
    "Z_BILLING":   486,
}


async def seed():
    async with AsyncSessionLocal() as db:

        # 1. Store
        await db.execute(text(
            "INSERT INTO stores (store_id, name, timezone, address) "
            "VALUES (:sid, :name, :tz, :addr) ON CONFLICT (store_id) DO NOTHING"
        ), {
            "sid": STORE_ID,
            "name": "VisionRetail Bangalore Central - Store 002",
            "tz": "Asia/Kolkata",
            "addr": "12, MG Road, Bangalore 560001",
        })
        print("  [1/7] Store upserted")

        # 2. Zones - pass polygon as text, cast inside SQL using cast(val as jsonb)
        for z in ZONES:
            poly_str = json.dumps(z["polygon"])
            await db.execute(text(
                "INSERT INTO zones (zone_id, store_id, name, zone_type, polygon_json, priority) "
                "VALUES (:zid, :sid, :name, :ztype, cast(:poly as jsonb), :pri) "
                "ON CONFLICT (zone_id) DO UPDATE "
                "SET name=EXCLUDED.name, zone_type=EXCLUDED.zone_type, "
                "    polygon_json=EXCLUDED.polygon_json, priority=EXCLUDED.priority"
            ), {
                "zid": z["zone_id"],
                "sid": STORE_ID,
                "name": z["name"],
                "ztype": z["zone_type"],
                "poly": poly_str,
                "pri": z["priority"],
            })
        print(f"  [2/7] {len(ZONES)} zones upserted")

        # 3. Visitor sessions + events
        total_sessions = 0
        for (hour, visitors, conversions, avg_dwell, max_queue, abandonments) in HOURLY_PATTERN:
            bucket_utc = datetime(TODAY.year, TODAY.month, TODAY.day, hour, 0, 0, tzinfo=timezone.utc) \
                         - timedelta(hours=5, minutes=30)
            for i in range(visitors):
                sess_id = uuid.uuid4()
                visitor_id = f"VIS_{hour}_{i:04d}"
                is_converted = i < conversions
                entry_t = bucket_utc + timedelta(minutes=random.randint(0, 55))
                dwell = max(30, int(random.gauss(avg_dwell, avg_dwell * 0.3)))
                exit_t = entry_t + timedelta(seconds=dwell)
                zones_visited = ["Z_ENTRANCE"]
                if i < int(visitors * 0.85):
                    zones_visited.append(random.choice([
                        "Z_SKINCARE", "Z_FRAGRANCE", "Z_MAKEUP",
                        "Z_HAIRCARE", "Z_WELLNESS", "Z_GIFTING"
                    ]))
                if is_converted:
                    zones_visited.append("Z_BILLING")

                await db.execute(text(
                    "INSERT INTO visitor_sessions "
                    "(session_id, store_id, visitor_id, track_ids, entry_time, exit_time, "
                    " dwell_seconds, is_converted, is_staff, is_reentry, zones_visited, "
                    " sequence_number, camera_id) "
                    "VALUES (:sid, :store, :vid, cast(:tracks as jsonb), :entry, :exit, "
                    "        :dwell, :conv, false, false, cast(:zones as jsonb), 1, 'CAM_01') "
                    "ON CONFLICT DO NOTHING"
                ), {
                    "sid": str(sess_id),
                    "store": STORE_ID,
                    "vid": visitor_id,
                    "tracks": "[]",
                    "entry": entry_t,
                    "exit": exit_t,
                    "dwell": float(dwell),
                    "conv": is_converted,
                    "zones": json.dumps(zones_visited),
                })

                # ENTRY and EXIT events
                await db.execute(text(
                    "INSERT INTO events "
                    "(event_id, store_id, session_id, visitor_id, event_type, "
                    " timestamp, zone_id, confidence, is_staff, camera_id) "
                    "VALUES (:eid, :store, :sess, :vid, 'ENTRY', "
                    "        :ts, 'Z_ENTRANCE', 0.97, false, 'CAM_01') "
                    "ON CONFLICT DO NOTHING"
                ), {
                    "eid": str(uuid.uuid4()),
                    "store": STORE_ID,
                    "sess": str(sess_id),
                    "vid": visitor_id,
                    "ts": entry_t,
                })
                
                await db.execute(text(
                    "INSERT INTO events "
                    "(event_id, store_id, session_id, visitor_id, event_type, "
                    " timestamp, zone_id, confidence, is_staff, camera_id) "
                    "VALUES (:eid, :store, :sess, :vid, 'EXIT', "
                    "        :ts, 'Z_ENTRANCE', 0.98, false, 'CAM_01') "
                    "ON CONFLICT DO NOTHING"
                ), {
                    "eid": str(uuid.uuid4()),
                    "store": STORE_ID,
                    "sess": str(sess_id),
                    "vid": visitor_id,
                    "ts": exit_t,
                })

                # Simulate REENTRY for a few visitors
                if random.random() < 0.05:
                    await db.execute(text(
                        "INSERT INTO events "
                        "(event_id, store_id, session_id, visitor_id, event_type, "
                        " timestamp, zone_id, confidence, is_staff, camera_id) "
                        "VALUES (:eid, :store, :sess, :vid, 'REENTRY', "
                        "        :ts, 'Z_ENTRANCE', 0.95, false, 'CAM_01') "
                        "ON CONFLICT DO NOTHING"
                    ), {
                        "eid": str(uuid.uuid4()),
                        "store": STORE_ID,
                        "sess": str(sess_id),
                        "vid": visitor_id,
                        "ts": entry_t + timedelta(seconds=10),
                    })
                # ZONE events for additional zones
                for zone_id in zones_visited[1:]:
                    zone_enter_t = entry_t + timedelta(seconds=random.randint(60, 180))
                    zone_dwell_secs = random.randint(30, 200)
                    zone_exit_t = zone_enter_t + timedelta(seconds=zone_dwell_secs)
                    
                    # ZONE_ENTER
                    await db.execute(text(
                        "INSERT INTO events "
                        "(event_id, store_id, session_id, visitor_id, event_type, "
                        " timestamp, zone_id, confidence, is_staff, camera_id) "
                        "VALUES (:eid, :store, :sess, :vid, 'ZONE_ENTER', "
                        "        :ts, :zone, 0.95, false, 'CAM_02') "
                        "ON CONFLICT DO NOTHING"
                    ), {
                        "eid": str(uuid.uuid4()),
                        "store": STORE_ID,
                        "sess": str(sess_id),
                        "vid": visitor_id,
                        "ts": zone_enter_t,
                        "zone": zone_id,
                    })
                    
                    # ZONE_DWELL
                    await db.execute(text(
                        "INSERT INTO events "
                        "(event_id, store_id, session_id, visitor_id, event_type, "
                        " timestamp, zone_id, confidence, is_staff, camera_id, metadata_json) "
                        "VALUES (:eid, :store, :sess, :vid, 'ZONE_DWELL', "
                        "        :ts, :zone, 0.96, false, 'CAM_02', cast(:meta as jsonb)) "
                        "ON CONFLICT DO NOTHING"
                    ), {
                        "eid": str(uuid.uuid4()),
                        "store": STORE_ID,
                        "sess": str(sess_id),
                        "vid": visitor_id,
                        "ts": zone_exit_t,
                        "zone": zone_id,
                        "meta": json.dumps({"dwell_seconds": zone_dwell_secs}),
                    })
                    
                    # ZONE_EXIT
                    await db.execute(text(
                        "INSERT INTO events "
                        "(event_id, store_id, session_id, visitor_id, event_type, "
                        " timestamp, zone_id, confidence, is_staff, camera_id) "
                        "VALUES (:eid, :store, :sess, :vid, 'ZONE_EXIT', "
                        "        :ts, :zone, 0.94, false, 'CAM_02') "
                        "ON CONFLICT DO NOTHING"
                    ), {
                        "eid": str(uuid.uuid4()),
                        "store": STORE_ID,
                        "sess": str(sess_id),
                        "vid": visitor_id,
                        "ts": zone_exit_t,
                        "zone": zone_id,
                    })

                # BILLING queues
                if is_converted or random.random() < 0.15: # 15% abandonment rate
                    join_t = exit_t - timedelta(seconds=random.randint(120, 300))
                    await db.execute(text(
                        "INSERT INTO events "
                        "(event_id, store_id, session_id, visitor_id, event_type, "
                        " timestamp, zone_id, confidence, is_staff, camera_id) "
                        "VALUES (:eid, :store, :sess, :vid, 'BILLING_QUEUE_JOIN', "
                        "        :ts, 'Z_BILLING', 0.98, false, 'CAM_03') "
                        "ON CONFLICT DO NOTHING"
                    ), {
                        "eid": str(uuid.uuid4()),
                        "store": STORE_ID,
                        "sess": str(sess_id),
                        "vid": visitor_id,
                        "ts": join_t,
                    })

                    if is_converted:
                        await db.execute(text(
                            "INSERT INTO events "
                            "(event_id, store_id, session_id, visitor_id, event_type, "
                            " timestamp, zone_id, confidence, is_staff, camera_id) "
                            "VALUES (:eid, :store, :sess, :vid, 'PURCHASE', "
                            "        :ts, 'Z_BILLING', 1.0, false, 'CAM_03') "
                            "ON CONFLICT DO NOTHING"
                        ), {
                            "eid": str(uuid.uuid4()),
                            "store": STORE_ID,
                            "sess": str(sess_id),
                            "vid": visitor_id,
                            "ts": exit_t - timedelta(seconds=random.randint(10, 30)),
                        })
                    else:
                        await db.execute(text(
                            "INSERT INTO events "
                            "(event_id, store_id, session_id, visitor_id, event_type, "
                            " timestamp, zone_id, confidence, is_staff, camera_id) "
                            "VALUES (:eid, :store, :sess, :vid, 'BILLING_QUEUE_ABANDON', "
                            "        :ts, 'Z_BILLING', 0.97, false, 'CAM_03') "
                            "ON CONFLICT DO NOTHING"
                        ), {
                            "eid": str(uuid.uuid4()),
                            "store": STORE_ID,
                            "sess": str(sess_id),
                            "vid": visitor_id,
                            "ts": join_t + timedelta(seconds=random.randint(20, 90)),
                        })

                total_sessions += 1

        print(f"  [3/7] {total_sessions} sessions + events inserted")

        print(f"  [3/7] {total_sessions} sessions + events inserted")

        # 4. Hourly metrics & 5. Daily metrics via aggregation engine
        for (hour, visitors, conversions, avg_dwell, max_queue, abandonments) in HOURLY_PATTERN:
            bucket_utc = datetime(TODAY.year, TODAY.month, TODAY.day, hour, 0, 0, tzinfo=timezone.utc) \
                         - timedelta(hours=5, minutes=30)
            
            await update_hourly_metrics(db, STORE_ID, bucket_utc)
            await update_daily_metrics(db, STORE_ID, bucket_utc.date())

        print("  [4/7] & [5/7] hourly_metrics and daily_metrics updated via aggregation engine")

        # 6. Anomalies via anomaly engine
        await run_anomaly_detection(db, STORE_ID, current_time=NOW, zscore_threshold=1.5, lookback_days=1)
        print("  [6/7] Anomalies generated via anomaly engine")

        await db.commit()

        print("")
        print("Seed complete!")
        print(f"  Store:       {STORE_ID}")
        print(f"  Zones:       {len(ZONES)}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
