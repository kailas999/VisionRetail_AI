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
