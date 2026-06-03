# CHOICES.md — VisionRetail AI Architecture Decision Record

This document records the three key architectural decisions made during the build of VisionRetail AI, including what alternatives were considered, what AI suggested, and what we ultimately chose — and why.

---

## Decision 1: Detection Model Selection

### Options Considered

| Model | Pros | Cons |
|---|---|---|
| **YOLOv8m** | Strong balance of speed and mAP; single-stage; well-maintained Ultralytics ecosystem; direct export to ByteTrack-compatible format | Slightly slower than nano/small variants |
| YOLOv8n (nano) | Fastest inference; lowest memory footprint | Lower mAP (~37 vs ~50.2); fails on partial occlusion in crowded billing scenes |
| RT-DETR | Transformer-based; SOTA accuracy | 3–5× slower than YOLOv8; no native ByteTrack integration |
| MediaPipe Pose | Works for body-part tracking | Not a person detector; fails group counting |
| GPT-4V / Gemini Vision | Can interpret scenes semantically | 200–2000ms per frame API latency; unusable for 15fps real-time; cost-prohibitive |

### What AI Suggested

When I prompted Claude to evaluate model trade-offs for a 15fps 1080p retail CCTV scenario with occlusion, it recommended YOLOv8m for the same reasons above and specifically flagged that YOLOv8n's lower mAP would hurt under the partial occlusion and group-entry edge cases described in the challenge. It also suggested considering RT-DETR but explicitly noted the latency issue for real-time use. I agreed with this assessment.

### What We Chose: **YOLOv8m**

**Rationale:** The 20-minute retail clips operate at 15fps. At our 4-frame batch size, YOLOv8m processes batches in ~80ms on CPU — well within the 266ms budget per frame. The medium model's higher mAP (50.2 vs 37.3 for nano) is critical for the billing queue scene where customers are partially behind counters. For staff detection, YOLOv8m's better recall means fewer staff-as-customer false positives contaminating the conversion funnel.

**VLM Usage:** We explicitly chose NOT to use a VLM (GPT-4V/Gemini Vision) for zone classification or staff detection. The latency (>200ms/frame) makes it non-viable for 15fps video. Instead, staff detection is rule-based (zone ubiquity + dwell pattern heuristics via `StaffDetector`) and zone classification is polygon-based via `ZoneClassifier`. If latency constraints were lifted (e.g., offline post-processing), a VLM prompt like `"Is this person wearing a uniform or staff badge? Respond: staff/customer"` with a bounding box crop would be a viable enhancement — but it would need caching and batching to be cost-effective.

---

## Decision 2: Event Schema Design Rationale

### Options Considered

**Option A — Flat event-per-action schema (chosen):**
Each discrete behavioural action (ENTRY, ZONE_ENTER, PURCHASE etc.) is its own row with a fixed schema. The `metadata` JSONB field absorbs event-specific fields (queue_depth, dwell_seconds, session_seq).

**Option B — Session-centric schema:**
One row per visitor session with arrays of zone visits and a final outcome. Simpler queries for session-level analytics but requires buffering entire sessions before writing — introduces latency and loses real-time streaming capability.

**Option C — Raw telemetry (frame-level bounding boxes):**
Store every detection with bbox coordinates. Maximally flexible but creates enormous storage volume (~162,000 rows per 20-minute clip at 15fps × 4 cameras). Completely unsuitable for the `events` query patterns required.

### What AI Suggested

Claude suggested a hybrid: use the flat event schema for the stream, but materialise session data asynchronously in a `visitor_sessions` table. This is exactly what we implemented — `ingest_events()` writes to `events` and simultaneously upserts to `visitor_sessions`. The AI's suggestion to use a deterministic UUID5 key (`visitor_id:store_id:date:seq`) for session deduplication was adopted directly — it ensures the same event replayed multiple times always maps to the same session row, making ingestion idempotent at the session level.

**One place I overrode AI:** Claude initially suggested storing the full `zones_visited` array as a normalised junction table (`session_zone_visits`). I rejected this — the junction table adds 2 extra joins to the funnel CTE, and the query planner can extract zone arrays from JSONB faster than joining a small array of zone IDs. For the event volumes in this problem (thousands per day vs millions), the simpler JSONB array wins on maintainability.

### What We Chose: **Flat event schema with JSONB metadata**

**Rationale:** The flat schema maps directly to the required event type catalogue. Each event type is independently queryable via `event_type = 'PURCHASE'` — no JSON parsing required for the critical funnel CTE. The JSONB `metadata` field absorbs optional fields (`queue_depth`, `dwell_seconds`, `session_seq`, `bbox`) without schema migration. This keeps the core schema stable as the pipeline evolves.

The `dwell_ms` field at the top level (not just in metadata) was a deliberate choice: the funnel and heatmap queries need dwell without parsing JSONB, which is a full table scan cost at scale.

---

## Decision 3: API Architecture — Synchronous Aggregation vs Background Tasks

### Options Considered

**Option A — Synchronous aggregation on every ingest (chosen for now):**
After each `POST /events/ingest` batch, `update_hourly_metrics()` and `update_daily_metrics()` are called in the same request-response cycle, then `run_anomaly_detection()` runs.

**Option B — Background async task (Celery/asyncio.create_task):**
Ingest returns immediately (fast 200), aggregation runs as a background task. Dashboard reads pre-computed metrics.

**Option C — Streaming aggregation (Apache Kafka + Flink):**
Full event streaming architecture. Excessive for this problem scope.

### What AI Suggested

Claude recommended Option B for production: "At 40 stores sending events in real time, synchronous aggregation becomes a bottleneck — every ingest call blocks until all metrics are recomputed." This is correct for the 40-store production scenario described in the follow-up questions section of the challenge spec.

**I chose Option A for this submission because:**
1. The submission operates on a single store with batch-replayed events — the latency of synchronous aggregation is not observable.
2. Option B requires a task queue (Celery + Redis) or `BackgroundTasks` — additional infrastructure that complicates the `docker compose up` acceptance gate.
3. The spec asks for "real-time — not cached from yesterday" for `/metrics`. Synchronous aggregation guarantees this property trivially.

**What I would change at scale:** Move to FastAPI `BackgroundTasks` for the aggregation step first (zero new infrastructure), then graduate to Celery once concurrent store count exceeds ~10. The anomaly detection in particular (which queries 7 days of history per check) is the first bottleneck.

**One place I agreed with AI:** Claude flagged that the current `run_anomaly_detection()` runs for every affected store-hour combination in the ingest batch — meaning a large catchup batch (100 events across 5 hours) runs anomaly detection 5 times synchronously. I added de-duplication by collecting `store_hours: set[tuple]` before the loop to ensure each hour is processed at most once per ingest call.

---

## Summary

| Decision | AI Input | Our Choice | Override? |
|---|---|---|---|
| Detection model | YOLOv8m recommended | YOLOv8m | No — agreed |
| No VLM for zone/staff | Noted latency concern | Rule-based polygon + heuristic | Agreed |
| Session UUID strategy | UUID5 deterministic key | Adopted directly | No |
| Zone visits storage | Normalised junction table | JSONB array | Yes — overrode for simplicity |
| Aggregation timing | Background tasks (Celery) | Synchronous (scope-appropriate) | Yes — deferred to scale |
