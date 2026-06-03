# Architectural Choices — VisionRetail AI

> Interview-ready decision rationale for all major architectural choices.

---

## 1. YOLOv8m — Detection Model

### Decision: YOLOv8m (medium)

**Alternatives Considered:**
| Model | Reason Rejected |
|-------|----------------|
| YOLOv8n (nano) | Too light — lower mAP, misses partial occlusions in dense crowds |
| YOLOv8x (xlarge) | Too slow for real-time (8-12ms vs 4-5ms per frame on GPU) |
| YOLOv5 | Older, YOLOv8 outperforms on COCO at same FPS |
| RT-DETR | Higher accuracy but transformer overhead, harder to deploy |
| Detectron2 | Heavy dependency, not optimised for edge deployment |

**Why YOLOv8m:**
- 43.3 mAP@COCO — best accuracy/speed ratio in the v8 family
- Single-stage: no separate region proposal (faster for CCTV real-time)
- Native Ultralytics ByteTrack integration
- Confidence threshold 0.35 tuned for indoor CCTV (not outdoor defaults of 0.5)

**Tradeoffs:**
- Slightly slower than YOLOv8n (~5ms vs ~2ms per frame)
- Higher accuracy critical for Re-ID (missed detections break tracking)

**Scalability:** For multi-camera deployments, run one YOLOv8m instance per camera on GPU worker.

**Failure Modes:**
- Poor lighting → drop confidence threshold to 0.25
- Crowded scenes → reduce NMS IoU to 0.3

---

## 2. ByteTrack — Multi-Object Tracking

### Decision: ByteTrack

**Alternatives Considered:**
| Tracker | Reason Rejected |
|---------|----------------|
| SORT | Discards low-confidence detections entirely — ID switches in occlusion |
| DeepSORT | Appearance-based, duplicates Re-ID work; heavier |
| StrongSORT | Good but adds unnecessary complexity for our Re-ID layer |
| MOTDT | Older, less maintained |

**Why ByteTrack:**
- Associates ALL detections (high + low confidence) in two-step matching
- Reduces track fragmentation under partial occlusion (shelves, other customers)
- 90-frame lost-track buffer handles temporary disappearances
- Simple IoU-based association is explainable and debuggable

**Tradeoffs:**
- IoU-only matching can cause ID switches if two persons cross paths
- Mitigated by our Hybrid Re-ID layer on top

**Failure Modes:**
- Twin/identical appearance: Re-ID can't distinguish → separate as distinct visitors

---

## 3. Hybrid Re-ID Engine Design

### Decision: OSNet + Temporal + Trajectory (0.6:0.2:0.2)

**Why NOT appearance-only Re-ID:**
- OSNet fails when lighting changes (e.g., customer moves from sunlit entrance to dim aisle)
- Similar clothing (multiple customers in white shirts) causes false merges
- Appearance-only is brittle under partial occlusion

**Hybrid Score = 0.6×OSNet + 0.2×Temporal + 0.2×Trajectory**

**Why these weights:**
- Appearance is still the dominant signal (0.6) when available and reliable
- Temporal (0.2): eliminates physically impossible matches (person can't teleport)
- Trajectory (0.2): adds spatial continuity constraint

**Why OSNet specifically:**
- Omni-scale feature learning captures both fine-grained (clothing texture) and large-scale features
- Market-1501 pretrained weights generalize well to retail environments
- 512-dim embedding is compact enough for real-time comparison

**Graceful degradation:** If OSNet fails to load, weights auto-redistribute to 0.5:0.5 temporal+trajectory.

**Threshold 0.65:** Conservative (false split > false merge in retail analytics — better to count two sessions than combine different people).

---

## 4. PostgreSQL — Database

### Decision: PostgreSQL 16 with asyncpg

**Alternatives Considered:**
| Database | Reason Rejected |
|----------|----------------|
| MongoDB | No native ACID transactions for conversion linking; weaker SQL analytics |
| ClickHouse | OLAP-only, poor for transactional session updates |
| SQLite | Not suitable for concurrent writes from pipeline + API |
| Redis | Good for caching but not primary store (persistence risk) |
| TimescaleDB | Good fit but adds complexity for modest data volumes |

**Why PostgreSQL:**
- Full ACID: conversion linking requires atomic session update + transaction insert
- JSONB for flexible event metadata without schema migration
- `INSERT ... ON CONFLICT DO NOTHING`: native idempotent ingestion
- Pre-aggregated tables + composite indexes: O(1) API response time
- asyncpg: native async protocol, 3-5× faster than psycopg2 for async FastAPI

**Pre-aggregation strategy:**
- `hourly_metrics` and `daily_metrics` are upserted on every ingestion batch
- API reads from pre-aggregated tables → no per-request full-table scans
- Tradeoff: slight write overhead, massive read benefit

---

## 5. FastAPI — Backend Framework

### Decision: FastAPI with asyncpg

**Alternatives Considered:**
| Framework | Reason Rejected |
|-----------|----------------|
| Flask | Synchronous by default; no native async DB support |
| Django REST | Heavy ORM, harder to use with asyncpg |
| Tornado | Older async paradigm, less ecosystem |
| Express (Node) | Python CV pipeline requires Python backend |

**Why FastAPI:**
- Native async: same event loop as asyncpg → no thread pool overhead
- Pydantic v2: automatic request validation + OpenAPI schema generation
- Dependency injection: clean DB session lifecycle per request
- Auto-generated OpenAPI docs (critical for interview demonstration)
- Trace ID middleware: every request gets UUID for log correlation

---

## 6. GPT-5.2 Copilot Design

### Decision: RAG architecture with strict grounding

**Why RAG over fine-tuning:**
- Store data changes every hour → fine-tuned model would be stale immediately
- RAG retrieves fresh context on every query
- No training cost, no GPU for inference beyond API calls

**Why strict grounding rules:**
- Retail decisions have financial consequences — hallucinated insights are dangerous
- Copilot must never say "probably X" without evidence X in the retrieved data
- Post-response validation enforces evidence citation

**INSUFFICIENT_DATA design:**
- When <1 metric retrieved, return INSUFFICIENT_DATA rather than guess
- Confidence automatically capped based on data coverage
- Transparent to users: they know the limitation, not misled by confident-sounding hallucinations

**Temperature 0.1:**
- Low temperature for factual, consistent responses
- Higher temperature would increase creativity but reduce reliability

---

## 📋 Likely Purplle Interview Questions

### Q: "How does your Re-ID handle two people wearing identical clothing?"

**A:** The temporal and trajectory signals still help disambiguate. If two people are at different positions or the time gap is too large for one person to be at the next location, Re-ID creates separate identities. The threshold is conservative (0.65) to prefer creating a new identity over merging — a false split (one person counted as two visits) is recoverable in analytics; a false merge (two people counted as one) is harder to correct.

### Q: "Why not use Kafka for event streaming?"

**A:** Kafka adds operational overhead (Zookeeper/KRaft, partition management, consumer groups) that isn't justified at this scale. A single store generates ~2,000 events/day. PostgreSQL with asyncpg handles this trivially with O(ms) ingestion. If we scale to 100+ stores with real-time dashboards, Kafka becomes worthwhile. For this challenge, the simplest reliable solution wins.

### Q: "How does the anomaly detection avoid false positives on the first day?"

**A:** The Z-score engine requires a minimum of 3 data points (3 hours of historical data at the same time-of-day). With fewer points, it returns no anomalies rather than triggering on insufficient baseline. The `confidence` score also automatically decreases with fewer data points, so even if something looks anomalous early, the confidence reflects the uncertainty.

### Q: "What happens if the AI Copilot GPT API goes down?"

**A:** The CopilotService has a try/except around the OpenAI call. On failure, it returns a structured `INSUFFICIENT_DATA` response with `confidence=0.0` rather than crashing. The dashboard displays a clear error message. The rest of the API (metrics, funnel, anomalies) continues working independently.

### Q: "How would you scale this to 500 stores?"

**A:** 
1. Add a connection pool manager (PgBouncer) in front of PostgreSQL
2. Run multiple uvicorn workers behind nginx
3. Move video processing to a task queue (Celery + Redis) 
4. Add a caching layer (Redis) for frequently-queried metrics
5. Shard PostgreSQL by store_id if needed
6. Only then would Kafka + microservices become justified
