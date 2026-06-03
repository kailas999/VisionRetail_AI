"""
Seed script — generates synthetic store data and populates the database.
Run once after migrations: python backend/seed_db.py
"""
import asyncio
import csv
import json
import random
import uuid
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import text
from app.database import get_db_context


STORE_ID = "STORE_BLR_002"
# Try to find datasets directory robustly in container or local runs
for candidate in [
    Path(__file__).parent / "datasets",
    Path(__file__).parent.parent / "datasets",
    Path("/app/datasets")
]:
    if candidate.exists():
        LAYOUT_PATH = candidate / "raw" / "store_layout.json"
        POS_CSV_PATH = candidate / "raw" / "pos_transactions.csv"
        break
else:
    LAYOUT_PATH = Path(__file__).parent.parent / "datasets" / "raw" / "store_layout.json"
    POS_CSV_PATH = Path(__file__).parent.parent / "datasets" / "raw" / "pos_transactions.csv"


async def seed():
    async with get_db_context() as db:
        print("🧹 Clearing old database tables...")
        await db.execute(text("TRUNCATE TABLE events, visitor_sessions, hourly_metrics, daily_metrics, anomalies CASCADE;"))
        await db.commit()

        print("🌱 Seeding database...")

        # ── Store ─────────────────────────────────────────────────────────
        await db.execute(
            text("""
                INSERT INTO stores (store_id, name, timezone)
                VALUES (:id, :name, :tz)
                ON CONFLICT (store_id) DO NOTHING
            """),
            {"id": STORE_ID, "name": "Purplle Bangalore South", "tz": "Asia/Kolkata"},
        )

        # ── Zones ─────────────────────────────────────────────────────────
        layout = json.loads(LAYOUT_PATH.read_text())
        for store in layout["stores"]:
            if store["store_id"] != STORE_ID:
                continue
            for z in store["zones"]:
                await db.execute(
                    text("""
                        INSERT INTO zones (zone_id, store_id, name, zone_type, polygon_json, priority)
                        VALUES (:zid, :sid, :name, :ztype, CAST(:poly AS jsonb), :pri)
                        ON CONFLICT (zone_id) DO NOTHING
                    """),
                    {
                        "zid": z["zone_id"],
                        "sid": STORE_ID,
                        "name": z["name"],
                        "ztype": z["zone_type"],
                        "poly": json.dumps(z["polygon"]),
                        "pri": z.get("priority", 0),
                    },
                )

        # ── 7-day hourly metrics baseline ─────────────────────────────────
        base_date = date.today() - timedelta(days=7)
        for day_offset in range(7):
            d = base_date + timedelta(days=day_offset)
            for hour in range(9, 21):  # store open 9am-9pm
                # Realistic traffic pattern: peak at 11am-1pm and 5pm-7pm
                base_visitors = random.randint(8, 25)
                if hour in (11, 12, 17, 18):
                    base_visitors = random.randint(25, 50)
                elif hour in (10, 13, 16, 19):
                    base_visitors = random.randint(15, 35)

                conversions = int(base_visitors * random.uniform(0.18, 0.32))
                queue_depth = random.randint(1, 5) if hour in (11, 12, 17, 18) else random.randint(0, 3)
                avg_dwell = random.uniform(300, 900)

                hour_bucket = datetime(d.year, d.month, d.day, hour, tzinfo=timezone.utc)
                await db.execute(
                    text("""
                        INSERT INTO hourly_metrics (
                            store_id, hour_bucket, unique_visitors, conversions,
                            avg_dwell_seconds, max_queue_depth, abandonment_count,
                            reentry_count, total_revenue, updated_at
                        ) VALUES (
                            :sid, :hb, :uv, :conv, :dwell, :queue, :abandon, :reentry, :revenue, NOW()
                        )
                        ON CONFLICT (store_id, hour_bucket) DO NOTHING
                    """),
                    {
                        "sid": STORE_ID,
                        "hb": hour_bucket,
                        "uv": base_visitors,
                        "conv": conversions,
                        "dwell": avg_dwell,
                        "queue": queue_depth,
                        "abandon": random.randint(0, 3),
                        "reentry": random.randint(0, 2),
                        "revenue": conversions * random.uniform(250, 1500),
                    },
                )

        print("✅ Seeded: store, zones, 7-day hourly metrics (no dummy visitor sessions)")
        today = date.today()

        # ── POS CSV ───────────────────────────────────────────────────────
        pos_rows = []
        for i in range(30):
            hour = random.randint(9, 20)
            ts = datetime(today.year, today.month, today.day, hour, random.randint(0, 59), tzinfo=timezone.utc)
            pos_rows.append({
                "tx_id": str(uuid.uuid4()),
                "amount": round(random.uniform(200, 3000), 2),
                "timestamp": ts.isoformat(),
                "pos_terminal_id": f"POS_{random.randint(1,3):02d}",
            })

        with open(POS_CSV_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["tx_id", "amount", "timestamp", "pos_terminal_id"])
            writer.writeheader()
            writer.writerows(pos_rows)

        print(f"✅ POS CSV written: {POS_CSV_PATH} ({len(pos_rows)} transactions)")
        print("✅ Database seed complete!")


if __name__ == "__main__":
    asyncio.run(seed())
