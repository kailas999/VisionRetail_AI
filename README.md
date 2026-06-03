# VisionRetail AI

VisionRetail AI is an advanced multi-camera retail intelligence platform designed to track, analyze, and optimize customer journeys throughout physical retail environments. 

The system unifies independent CCTV feeds into a continuous event stream, providing deep insights into foot traffic, zone engagement, conversion funnels, and checkout efficiency—all accessible via a beautiful, real-time dashboard powered by GPT-5.2 insights.

## Features

- **Multi-Camera Re-ID**: Unifies cross-camera streams (Entrance, Zones, Checkout) using OSNet for persistent tracking across the store layout.
- **Funnel Analytics**: Mathematically guaranteed funnel tracking (Purchase ≤ Billing ≤ Engagement ≤ Entry) for highly accurate conversion rate monitoring.
- **Zone Heatmaps**: High-resolution dwell time and zone engagement heatmapping using real-time spatial awareness.
- **Anomaly Detection**: Automated statistical baseline checking with Z-score thresholds to instantly detect traffic collapses, dead zones, and queue spikes.
- **AI Store Intelligence**: GPT-5.2 powered executive summaries providing revenue risk analysis, top opportunities, and actionable recommendations securely grounded in deterministic metrics.

## System Architecture

VisionRetail AI breaks down the retail environment into three distinct analytical zones:

- **CAM_01**: Main Entry/Exit (Tracking `ENTRY`, `EXIT`, `REENTRY`)
- **CAM_02**: Store Floor (Tracking `ZONE_ENTER`, `ZONE_EXIT`, `ZONE_DWELL`)
- **CAM_03**: Checkout/Billing (Tracking `BILLING_QUEUE_JOIN`, `BILLING_QUEUE_ABANDON`, `PURCHASE`)

These raw events pass through a sophisticated Detection & Re-ID layer before being streamed to our Analytics Engine.

## Technology Stack

- **Backend**: FastAPI, PostgreSQL, SQLAlchemy (Async), Uvicorn
- **Frontend**: React 18, TypeScript, Vite, Recharts, TailwindCSS, Lucide Icons
- **AI/ML**: PyTorch, Ultralytics YOLOv8m (Object Detection), OSNet (Re-ID), OpenAI GPT-5.2 (Copilot Insights)
- **Infrastructure**: Docker, Docker Compose

## Project Structure

```text
visionretail_ai/
├── ai/                 # OpenAI prompts, LLM client, and retrieval logic
├── backend/            # FastAPI application (app/), database schemas, api routes, core services
├── datasets/           # Raw and processed datasets, including synthetic events payload
├── docs/               # System documentation, design specifications, and runbooks
├── frontend/           # React frontend application (Vite + TypeScript)
├── models/             # Local ML model weights (e.g., yolov8m.pt)
├── pipeline/           # Computer Vision pipeline (Detection, Tracking, Re-ID)
├── scripts/            # Utility scripts (seed data, mock generation)
├── tests/              # Unit and integration tests for backend services
├── docker-compose.yml  # Multi-container orchestration
└── README.md           # Project overview
```

## Installation

### Prerequisites
- Docker and Docker Compose
- Node.js (v18+) and Bun (if running frontend locally outside Docker)
- Python 3.11+ (if running backend locally outside Docker)

### Environment Variables
Copy the provided `.env.example` to `.env`:
```bash
cp .env.example .env
```
Ensure you add a valid `OPENAI_API_KEY` in the `.env` file for the AI Copilot and Store Intelligence features to function.

## Running with Docker (Recommended)

Start the entire stack (Database, API, Frontend):
```bash
cp .env.example .env          # 1. copy env (add OPENAI_API_KEY if desired)
docker compose up --build -d  # 2. start DB + API + Frontend
```
- **Dashboard**: http://localhost:3000
- **API Swagger**: http://localhost:8000/docs
- **Healthcheck**: http://localhost:8000/health

### Seeding the Database with Demo Data

If the dashboard shows no data, run the seeder inside the API container:
```bash
docker exec visionretail_api python /app/backend/seed_data.py
```
Wait ~10 seconds, then refresh the dashboard.

---

## Running the Detection Pipeline Against CCTV Clips

> This stage processes raw video clips through the YOLOv8m → ByteTrack → OSNet → Event pipeline and streams the resulting events into the running API.

### Prerequisites

```bash
pip install -r backend/requirements.txt   # install pipeline dependencies
```

### Step 1 — Place your clips

Place your CCTV video files into `data/videos/`:
```
data/videos/
├── cam_entry.mp4      # CAM_01 — Entry/Exit threshold
├── cam_floor.mp4      # CAM_02 — Main store floor
└── cam_billing.mp4    # CAM_03 — Checkout/billing area
```

You can also provide a `store_layout.json` at `data/store_layout.json` (see `datasets/` for an example).

### Step 2 — Run the pipeline (all cameras)

```bash
chmod +x pipeline/run.sh
./pipeline/run.sh \
    --store  STORE_BLR_002 \
    --layout data/store_layout.json \
    --output events.jsonl \
    --api-url http://localhost:8000
```

This processes all three camera clips, writes every generated event to `events.jsonl`, and automatically batch-ingests them into `POST /events/ingest` in chunks of 500.

### Run a single clip

```bash
./pipeline/run.sh \
    --video  data/videos/cam_entry.mp4 \
    --store  STORE_BLR_002 \
    --layout data/store_layout.json
```

### Dry-run (generate events.jsonl without ingesting)

```bash
./pipeline/run.sh --dry-run
```

### Step 3 — Verify ingestion

```bash
curl http://localhost:8000/stores/STORE_BLR_002/metrics
```

### Manual ingest from events.jsonl (Python)

```python
import json, httpx

events = [json.loads(line) for line in open("events.jsonl")]
for i in range(0, len(events), 500):
    batch = events[i:i+500]
    r = httpx.post("http://localhost:8000/events/ingest", json={"events": batch}, timeout=30)
    print(r.json())
```

---

## Running without Docker

### 1. Database Setup
Ensure you have PostgreSQL running. Update your `.env` with the correct `DATABASE_URL`.
### 2. Backend Startup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
### 3. Frontend Startup
```bash
cd frontend
bun install
bun run dev
```

## Dashboard Features

- **Live Analytics Panel**: Monitor total/unique visitors, current occupancy, and conversion rates.
- **Conversion Funnel**: Visually diagnose drop-offs between store entry and final purchase.
- **Zone Heatmap**: Analyze footfall and dwell time per aisle to identify hot spots and dead zones.
- **AI Store Intelligence**: Always-visible GPT-5.2 store performance summary, detailing top opportunities and revenue risks.
- **Anomaly Feed**: Real-time notifications for sudden queue spikes or traffic drops, augmented with AI-generated root-cause insights.

## Future Improvements

- Add WebSocket support for true real-time event streaming to the dashboard.
- Migrate Re-ID feature vectors to a dedicated vector database (e.g., pgvector, Milvus).
- Provide deeper integration for custom store layouts (drag-and-drop zone configuration).

## Contributing
Please see the `docs/` folder for detailed design choices, architecture specs, and runbooks before contributing. Ensure all tests pass before opening a Pull Request.

## License
MIT License



# Design Document: VisionRetail AI

## Business Problem
Brick-and-mortar retail operators often lack the granular analytics enjoyed by e-commerce platforms. While foot traffic counters exist, they fail to track the complete customer journey. Retailers struggle to measure zone engagement, monitor checkout queue abandonment, or understand conversion bottlenecks because camera systems are siloed and un-unified.

## Retail Intelligence Goals
VisionRetail AI aims to bridge the physical-digital analytics gap by providing:
1. **End-to-End Funnel Visibility**: Tracking users from entry, to product engagement, to purchase.
2. **Unified Customer Journeys**: Re-identifying the same shopper across multiple non-overlapping camera feeds.
3. **Actionable AI Insights**: Moving beyond raw data to provide automated root-cause analysis and operational recommendations using GPT-5.2.

## Architecture Decisions

### Detection Layer
- **YOLOv8m**: Chosen for its balance of speed and accuracy. It successfully detects human subjects across varying camera angles (overhead and angled) required for retail environments.
- **DeepSORT Tracking**: Implements temporal consistency, ensuring a person is tracked robustly within a single camera feed even through brief occlusions.

### Tracking Layer & Event Stream
- Events are decoupled from video frames. As subjects cross defined polygons (e.g., entrance lines or zone boundaries), discrete semantic events (`ENTRY`, `ZONE_ENTER`, `PURCHASE`) are emitted.
- This creates an incredibly lightweight `events` table in PostgreSQL, vastly reducing the storage required compared to storing raw video or continuous frame metadata.

### Re-ID Layer
- **OSNet**: Utilized for cross-camera Re-Identification (Re-ID). OSNet generates a high-dimensional feature vector for each detected subject.
- **Cosine Similarity Matching**: By comparing OSNet feature vectors, the system can reliably link a `CAM_01` (Entry) visitor to a `CAM_03` (Checkout) visitor, collapsing fragmented sessions into a single unified `visitor_id`.

### Analytics Engine
- **Funnel Mathematical Guarantee**: The analytics engine utilizes a boolean multiplication CTE (`has_entry × has_engagement × has_billing × has_purchase`). This mathematically enforces the strict hierarchy of the retail funnel (`Purchase <= Billing <= Engagement <= Entry`), ensuring absolute data integrity.
- **Pre-Aggregation**: Hourly and daily metrics are rolled up via periodic tasks to ensure rapid dashboard load times.

### AI Insight Layer (GPT-5.2)
- **Design Philosophy**: GPT-5.2 is used exclusively for *explanation*, never for *detection*.
- **Mechanism**: The backend first computes deterministic statistics (Z-scores, conversion rates, visitor counts). These facts are securely injected into a prompt template, ensuring the LLM is grounded in mathematical reality.
- **Fallback Mechanisms**: If OpenAI APIs are unreachable, the system automatically falls back to robust, rule-based deterministic insights to guarantee 100% dashboard uptime.

## Tradeoffs

- **Edge vs Cloud Compute**: The current architecture runs the CV pipeline (YOLO/OSNet) locally or on-prem. While this reduces bandwidth and latency, it requires significant local GPU/CPU resources.
- **Database Search**: Currently, Re-ID matching relies on naive vector matching. As the dataset scales, this will become an $O(N^2)$ bottleneck.
- **Relational vs Timeseries DB**: PostgreSQL is used for simplicity, but a dedicated timeseries database (like TimescaleDB) would be more efficient for the event stream at scale.

## Scalability Considerations
- **Stateless API**: The FastAPI backend is entirely stateless, allowing it to be horizontally scaled behind a load balancer.
- **Event Bus**: The CV pipeline currently writes directly to the database. At scale, an event bus (Kafka/RabbitMQ) should be introduced to decouple video processing from database ingestion.

## Failure Recovery
- **LLM Degradation**: Implemented a 15-minute TTLCache and hardcoded fallback templates to survive OpenAI outages.
- **Camera Drops**: The system is designed to gracefully handle missed detections. The funnel logic uses `MAX()` logic across the day to ensure partial journeys are still captured.

## Future Improvements
- Migration of Re-ID feature vectors to pgvector for index-accelerated nearest-neighbor searches.
- Migration to WebSockets for sub-second real-time dashboard updates.
- Implementation of a distributed message queue for event ingestion.

---

## AI-Assisted Decisions

The following three decisions were shaped materially by LLM consultation during the design phase. For each, we document the AI's input, whether we agreed or overrode it, and why.

### 1. Session Identity Key Strategy

**LLM consulted:** Claude  
**Prompt:** *"I'm building an event ingestion system where the same visitor can appear across 3 cameras. How should I generate a session UUID that is deterministic (for idempotency) but also deduplicates cross-camera events into one session?"*

**AI suggested:** Use `uuid.uuid5(NAMESPACE_OID, f"{visitor_id}:{store_id}:{date}:{session_seq}")` — a deterministic namespace UUID that produces the same session UUID for the same visitor on the same date. This means re-ingesting the same event batch produces the exact same session rows.

**We agreed.** This is now implemented in [ingestion.py](file:///d:/VisionRetail_AI-main/backend/app/services/ingestion.py). The AI's reasoning was correct: UUID5 provides idempotency at the session level without needing a separate deduplication table.

---

### 2. Funnel Hierarchy Guarantee

**LLM consulted:** Claude  
**Prompt:** *"How do I ensure that in a retail funnel (Entry → Zone → Billing → Purchase), the counts are always monotonically decreasing? I've seen production systems where Purchase > Entry due to bugs."*

**AI suggested:** Use boolean multiplication in a CTE: `(has_entry × has_engagement × has_billing × has_purchase)`. This makes it mathematically impossible for any downstream stage to exceed an upstream stage, because each flag is 0 or 1, and a person can only reach `reached_purchase = 1` if every prior flag is also 1.

**We agreed and extended it.** The CTE in [metrics.py](file:///d:/VisionRetail_AI-main/backend/app/api/metrics.py) uses this exact pattern, shared between both `/funnel` and `/metrics` endpoints so the numbers are always identical. We added an additional runtime assertion that logs a warning if upstream data somehow violates the hierarchy — a defense-in-depth measure the AI did not suggest.

---

### 3. Anomaly Detection: Z-Score vs Rule-Based Thresholds

**LLM consulted:** Claude  
**Prompt:** *"I need to detect anomalies like queue spikes and conversion drops in a retail store. Should I use fixed thresholds (e.g., queue > 10) or statistical methods?"*

**AI suggested:** Z-score against a rolling 7-day same-hour baseline. Reason: fixed thresholds don't adapt to store-specific patterns (a flagship store has naturally higher queues than a kiosk). Z-score with a 7-day lookback captures seasonal patterns within a week while being robust to single outliers.

**We agreed, but overrode the baseline window.** The AI initially suggested a 30-day lookback. We reduced it to 7 days for two reasons: (1) retail patterns shift weekly (promotions, weekends), so a 30-day average blends different traffic regimes; (2) the challenge runs on shorter clip datasets where 30-day history doesn't exist. We also added the `n < 3` insufficient-data guard (returning `None` instead of a meaningless z-score) which the AI's initial code omitted.

