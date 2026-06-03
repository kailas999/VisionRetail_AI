# Architecture — VisionRetail AI

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INPUT LAYER                                  │
│  datasets/raw/CCTV_Footage/   datasets/raw/store_layout.json        │
│  CAM 1-5.mp4                  pos_transactions.csv                  │
└────────────────────┬────────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    CV PIPELINE  (pipeline/)                         │
│                                                                     │
│   detector.py        YOLOv8m — person detection @ conf=0.35         │
│       ↓                                                             │
│   tracker.py         ByteTrack — persistent track IDs              │
│       ↓                                                             │
│   reid_engine.py     Hybrid Re-ID:                                  │
│                        0.6 × OSNet appearance                       │
│                        0.2 × Temporal (exponential decay)           │
│                        0.2 × Trajectory (IoU extrapolation)         │
│       ↓                                                             │
│   zone_classifier.py Shapely point-in-polygon (store_layout.json)   │
│       ↓                                                             │
│   staff_detector.py  Multi-signal: duration+coverage+repeat+hours   │
│       ↓                                                             │
│   queue_detector.py  Billing zone density + dwell timeout           │
│       ↓                                                             │
│   event_generator.py UUID events, session tracking, dedup           │
│       ↓                                                             │
│   video_processor.py Orchestrator — runs all above per frame        │
└────────────────────┬────────────────────────────────────────────────┘
                     │  Generated Events (JSONL / API POST)
                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   FASTAPI BACKEND  (backend/)                       │
│                                                                     │
│   POST /events/ingest      → services/ingestion.py                 │
│       → ON CONFLICT DO NOTHING (idempotent UUID dedup)              │
│       → services/aggregation.py  (upsert hourly + daily metrics)    │
│       → services/anomaly.py      (Z-score anomaly run)              │
│                                                                     │
│   GET  /stores/{id}/metrics    → daily_metrics table (O(1))         │
│   GET  /stores/{id}/funnel     → events CTE query                   │
│   GET  /stores/{id}/heatmap    → zones + ZONE_DWELL events          │
│   GET  /stores/{id}/anomalies  → anomalies table (unresolved)       │
│   POST /copilot/query          → ai/ RAG pipeline                   │
│   GET  /health                 → DB ping                            │
└────────────────────┬────────────────────────────────────────────────┘
                     │
         ┌───────────┴──────────────┐
         ▼                          ▼
┌──────────────────┐    ┌───────────────────────────────────────────┐
│   POSTGRESQL     │    │    AI COPILOT  (ai/)                       │
│                  │    │                                           │
│   events         │    │  retrieval/store_retriever.py             │
│   visitor_sess.. │    │    → fetches metrics, funnel,             │
│   transactions   │    │      anomalies, heatmap from DB           │
│   hourly_metrics │    │                                           │
│   daily_metrics  │    │  prompts/copilot_prompts.py               │
│   anomalies      │    │    → SYSTEM_PROMPT (strict grounding)     │
│   stores         │    │                                           │
│   zones          │    │  llm_client.py                            │
└──────────────────┘    │    → async GPT-5.2 call, JSON response    │
                        └───────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│               STREAMLIT DASHBOARD  (frontend/)                      │
│                                                                     │
│   01_Overview.py   KPI cards + hourly traffic chart (5s refresh)    │
│   02_Funnel.py     Entry→Zone→Billing→Converted funnel chart        │
│   03_Heatmap.py    Zone floor plan + dwell intensity heatmap        │
│   04_Anomalies.py  Anomaly cards with gauge + recommendations       │
│   05_Copilot.py    AI chat interface with evidence display          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Detail

### Event Ingestion Path
```
video → pipeline → events.jsonl
                       ↓
              POST /events/ingest
                       ↓
         INSERT events ON CONFLICT DO NOTHING
                       ↓
         UPSERT visitor_sessions
                       ↓
         UPSERT hourly_metrics (per hour)
                       ↓
         UPSERT daily_metrics (per day)
                       ↓
         Run Z-score anomaly detection
```

### Read Path (O(1) metrics)
```
GET /stores/STORE_BLR_002/metrics?date=2026-05-30
                       ↓
  SELECT * FROM daily_metrics WHERE store_id=? AND date_bucket=?
  [indexed, single row, no aggregation at read time]
```

---

## Database Schema

```
stores ──┬── zones
         ├── visitor_sessions ──── events
         │                    └── transactions
         ├── hourly_metrics
         ├── daily_metrics
         └── anomalies
```

---

## Folder Responsibilities

| Folder | Responsibility |
|--------|----------------|
| `datasets/` | All data: raw inputs, processed outputs, events |
| `models/` | Pre-trained model weights (.pt, .pth) |
| `pipeline/` | Computer vision: detect → track → reid → classify → generate |
| `backend/` | FastAPI API, DB models, services, migrations |
| `ai/` | LLM client, prompt templates, retrieval layer |
| `frontend/` | Streamlit 5-page dashboard |
| `tests/` | Unit, integration, API, pipeline, AI tests |
| `docs/` | All design documentation |
