# Runbook: VisionRetail AI

This runbook provides step-by-step instructions for deploying, verifying, and troubleshooting the VisionRetail AI platform.

## Prerequisites

Before starting, ensure the following are installed:
- [Docker Engine](https://docs.docker.com/engine/install/) & [Docker Compose](https://docs.docker.com/compose/install/)
- (Optional for local dev) Node.js v18+, Bun, Python 3.11+

## Environment Setup

1. Clone the repository and navigate to the project root:
   ```bash
   cd visionretail_ai
   ```
2. Create the `.env` file from the example:
   ```bash
   cp .env.example .env
   ```
3. Open `.env` and add your `OPENAI_API_KEY`. (The backend will still function without it, but AI insights will gracefully fallback to rule-based logic).

## Docker Startup (Recommended)

The easiest way to run the entire system (Database, Backend API, and Frontend) is via Docker Compose.

1. Build and launch all containers in detached mode:
   ```bash
   docker compose up --build -d
   ```
2. Verify all containers are running:
   ```bash
   docker compose ps
   ```
   *Expected Output*: You should see `visionretail_db`, `visionretail_api`, and `visionretail_frontend` all marked as `Up (healthy)` or `Up`.

## Manual Startup (Without Docker)

If you prefer to run services natively:

### 1. PostgreSQL Setup
Start a local Postgres instance on port 5432. Ensure your `.env` `DATABASE_URL` matches your local credentials.

### 2. Backend Startup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run migrations (creates tables)
alembic upgrade head

# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend Startup
```bash
cd frontend
bun install
bun run dev
```

## Health Checks & API Verification

Once the system is running, verify the backend is responsive.

1. **Check API Health**:
   ```bash
   curl http://localhost:8000/health
   ```
   *Expected Response*:
   ```json
   {
     "status": "ok",
     "version": "1.0.0"
   }
   ```

2. **Check Dashboard**:
   Open a browser and navigate to `http://localhost:3000`.

3. **Verify Event Stream / Metrics**:
   ```bash
   curl "http://localhost:8000/stores/STORE_BLR_002/metrics"
   ```
   *Expected Response*: Returns a JSON payload containing `unique_visitors`, `conversion_rate`, `hourly_breakdown`, etc.

## Troubleshooting

### Issue: Dashboard says "Connection Refused"
- **Cause**: The frontend container failed to build or start.
- **Fix**: Check frontend logs via `docker compose logs -f frontend`. If it's a build error, ensure `bun` is correctly installed in the image or fix the local TypeScript error preventing compilation.

### Issue: "OpenAI call failed" in logs / UI shows "Rule-Based Mode"
- **Cause**: The `OPENAI_API_KEY` is missing or invalid, or the API is rate-limited.
- **Fix**: Check the `.env` file, ensure the API key has active credits. The system is designed to gracefully fallback to deterministic recommendations when this occurs, so no core functionality is broken.

### Issue: Database migrations fail on startup
- **Cause**: The `api` container attempted to run `alembic upgrade head` before the `db` container was fully ready.
- **Fix**: Docker Compose `depends_on: condition: service_healthy` handles this. If running manually, ensure Postgres is accepting connections before starting the API.

### Issue: No data appearing in dashboard
- **Cause**: The database is empty.
- **Fix**: Run the data seeder script:
   ```bash
   cd backend
   python seed_data.py
   ```
   Wait 1-2 minutes for the system to populate simulated CV events. Refresh the dashboard.
