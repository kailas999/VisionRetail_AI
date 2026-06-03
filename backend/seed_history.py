"""
seed_history.py — Backfill 7 days of realistic hourly metrics and trigger anomaly detection.

Run inside the API container:
    docker exec visionretail_api python /app/backend/seed_history.py

Purpose:
  The Z-score anomaly engine needs >= 3 data points of the SAME HOUR across multiple
  days to compute a meaningful baseline. With only 1 day of data (today), no anomalies
  are ever triggered. This script backfills 7 days of hourly_metrics with realistic
  patterns and deliberately introduces anomalies in the most recent hours.
"""
import asyncio
import random
import sys
import os
from datetime import datetime, date, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(__file__))
from app.config import get_settings
from app.services.anomaly import run_anomaly_detection

settings = get_settings()
DATABASE_URL = settings.database_url
print(f"Connecting to: {DATABASE_URL}")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

STORE_ID = "STORE_BLR_002"
NOW = datetime.now(timezone.utc)
TODAY = NOW.replace(minute=0, second=0, microsecond=0)

# ── Realistic hourly traffic patterns (hour → base_visitors) ──────────────────
HOURLY_PATTERN = {
    9:  (30, 0.18, 2),   # (visitors, conversion_rate, max_queue)
    10: (55, 0.22, 3),
    11: (80, 0.25, 4),
    12: (110, 0.27, 6),
    13: (95, 0.24, 5),
    14: (70, 0.21, 4),
    15: (85, 0.23, 5),
    16: (100, 0.26, 7),
    17: (120, 0.28, 8),
    18: (130, 0.30, 10),
    19: (90, 0.24, 6),
    20: (60, 0.20, 3),
}

def jitter(value: float, pct: float = 0.15) -> float:
    """Add ±pct% random noise to a value."""
    return max(0.0, value * (1 + random.uniform(-pct, pct)))


async def backfill_history(db: AsyncSession):
    """Insert 7 days of hourly_metrics (days -7 to -1 relative to today)."""
    random.seed(42)  # reproducible
    inserted = 0

    for day_offset in range(7, 0, -1):  # 7 days ago → 1 day ago
        day_start = TODAY - timedelta(days=day_offset)

        for hour, (base_visitors, base_conv, base_queue) in HOURLY_PATTERN.items():
            bucket = day_start.replace(hour=hour)

            visitors   = int(jitter(base_visitors, 0.20))
            conv_rate  = jitter(base_conv, 0.15)
            conversions = int(visitors * conv_rate)
            queue      = int(jitter(base_queue, 0.25))
            abandon    = int(queue * jitter(0.15, 0.3))
            dwell      = jitter(180.0, 0.20)  # ~180 seconds avg dwell
            revenue    = conversions * jitter(850.0, 0.30)  # ~₹850 per purchase

            await db.execute(text("""
                INSERT INTO hourly_metrics
                    (store_id, hour_bucket, unique_visitors, staff_count, conversions,
                     avg_dwell_seconds, max_queue_depth, abandonment_count, reentry_count,
                     zone_dwell_json, total_revenue)
                VALUES
                    (:store_id, :bucket, :visitors, 2, :conversions,
                     :dwell, :queue, :abandon, 0,
                     '{}', :revenue)
                ON CONFLICT (store_id, hour_bucket) DO NOTHING
            """), {
                "store_id": STORE_ID,
                "bucket": bucket,
                "visitors": visitors,
                "conversions": conversions,
                "dwell": round(dwell, 1),
                "queue": queue,
                "abandon": abandon,
                "revenue": round(revenue, 2),
            })
            inserted += 1

    await db.commit()
    print(f"  ✅ Backfilled {inserted} hourly_metric rows (7 days history)")


async def inject_anomalies_now(db: AsyncSession):
    """
    Force the current hour to have anomalous values so the Z-score engine triggers.
    We manipulate the EXISTING today row to deviate sharply from the 7-day baseline.
    """
    current_hour = TODAY

    # Check if current hour row exists
    row = (await db.execute(
        text("SELECT * FROM hourly_metrics WHERE store_id=:s AND hour_bucket=:h"),
        {"s": STORE_ID, "h": current_hour}
    )).fetchone()

    if row:
        # QUEUE SPIKE: set max_queue_depth to 3× the typical value (~10 → 30)
        # CONVERSION DROP: drop conversion rate to near 0
        # TRAFFIC DROP: halve the typical visitor count
        await db.execute(text("""
            UPDATE hourly_metrics
            SET
                max_queue_depth   = 35,
                conversions       = 5,
                unique_visitors   = 15,
                abandonment_count = 18
            WHERE store_id = :s AND hour_bucket = :h
        """), {"s": STORE_ID, "h": current_hour})
        await db.commit()
        print(f"  ✅ Injected anomalous values into hour_bucket={current_hour.hour}:00")
    else:
        # Insert an anomalous row for the current hour if it doesn't exist
        await db.execute(text("""
            INSERT INTO hourly_metrics
                (store_id, hour_bucket, unique_visitors, staff_count, conversions,
                 avg_dwell_seconds, max_queue_depth, abandonment_count, reentry_count,
                 zone_dwell_json, total_revenue)
            VALUES
                (:s, :h, 15, 2, 5, 90.0, 35, 18, 0, '{}', 4250.0)
            ON CONFLICT (store_id, hour_bucket) DO UPDATE SET
                unique_visitors=EXCLUDED.unique_visitors,
                conversions=EXCLUDED.conversions,
                max_queue_depth=EXCLUDED.max_queue_depth,
                abandonment_count=EXCLUDED.abandonment_count
        """), {"s": STORE_ID, "h": current_hour})
        await db.commit()
        print(f"  ✅ Inserted anomalous row for hour_bucket={current_hour.hour}:00")


async def run_detection(db: AsyncSession):
    """Run anomaly detection for each hour that has data today."""
    hours_with_data = (await db.execute(
        text("""
            SELECT hour_bucket FROM hourly_metrics
            WHERE store_id=:s AND DATE(hour_bucket AT TIME ZONE 'UTC') = :d
            ORDER BY hour_bucket
        """),
        {"s": STORE_ID, "d": TODAY.date()}
    )).fetchall()

    total_new = 0
    for row in hours_with_data:
        bucket_time = row.hour_bucket
        new = await run_anomaly_detection(
            db,
            store_id=STORE_ID,
            current_time=bucket_time + timedelta(minutes=1),  # just after the hour
            zscore_threshold=2.5,
            lookback_days=7,
        )
        if new:
            total_new += len(new)
            for a in new:
                print(f"    🚨 {a['type']} | severity={a['severity']} | z={a['z_score']:.2f} | current={a['metric_value']:.1f} vs baseline={a['baseline_value']:.1f}")

    await db.commit()
    print(f"  ✅ Anomaly detection complete — {total_new} new anomalies generated")
    return total_new


async def main():
    print("\n🔧  VisionRetail AI — Historical Data & Anomaly Seeder")
    print("=" * 60)

    async with AsyncSessionLocal() as db:
        print("\n[1/3] Backfilling 7 days of hourly_metrics history…")
        await backfill_history(db)

        print("\n[2/3] Injecting anomalous values into current hour…")
        await inject_anomalies_now(db)

        print("\n[3/3] Running Z-score anomaly detection across today's hours…")
        count = await run_detection(db)

    await engine.dispose()

    print("\n" + "=" * 60)
    if count > 0:
        print(f"✅  Done! {count} anomalies are now active in the dashboard.")
    else:
        print("⚠️   No anomalies triggered (z-scores below threshold).")
        print("    Try re-running after more hours of data accumulate.")
    print("    Refresh the dashboard to see the Active Anomalies panel.\n")


if __name__ == "__main__":
    asyncio.run(main())
