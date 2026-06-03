"""
FastAPI application entry point.

Design:
- Lifespan context manager for DB startup/shutdown (no deprecated on_event).
- Trace ID middleware: injects UUID trace_id into every request context.
- CORS enabled for Streamlit dashboard.
- Structured JSON logging on startup.
- OpenAPI docs at /docs (disabled in production via env).
- ReIDService lifecycle management for analytics ingestion.
"""
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import engine
from app.utils.logging import configure_logging, get_logger, request_trace_id
from app.api import events, metrics, heatmap, anomalies, copilot, health, event_stream
from app.services.reid_service import ReIDService

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    logger.info(
        "VisionRetail API starting",
        extra={"environment": settings.environment, "model": settings.openai_model},
    )
    # Start Re-ID service
    app.state.reid_service = ReIDService()
    await app.state.reid_service.start()

    yield

    # Stop Re-ID service and DB
    await app.state.reid_service.stop()
    await engine.dispose()
    logger.info("VisionRetail API shutdown complete")


app = FastAPI(
    title="VisionRetail AI — Store Intelligence API",
    description=(
        "AI-powered retail store intelligence: detection, tracking, "
        "anomaly detection, and GPT-5.2 copilot."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url="/redoc",
)

# ── CORS ───────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Trace ID Middleware ──────────────────────────────────────────────────────────
@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    import time
    trace_id = request.headers.get("X-Trace-ID") or str(uuid.uuid4())
    token = request_trace_id.set(trace_id)
    start_time = time.monotonic()

    # Extract store_id from URL path (/stores/{store_id}/...)
    path_parts = request.url.path.strip("/").split("/")
    store_id = path_parts[1] if len(path_parts) >= 2 and path_parts[0] == "stores" else None

    try:
        response = await call_next(request)
        latency_ms = round((time.monotonic() - start_time) * 1000, 1)
        response.headers["X-Trace-ID"] = trace_id

        log_extra: dict = {
            "trace_id": trace_id,
            "endpoint": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
        }
        if store_id:
            log_extra["store_id"] = store_id

        logger.info("Request completed", extra=log_extra)
        return response
    except Exception as e:
        latency_ms = round((time.monotonic() - start_time) * 1000, 1)
        error_str = str(e).lower()
        if "cannot connect" in error_str or "connection refused" in error_str or "timeout" in error_str or "database is unavailable" in error_str or "getaddrinfo failed" in error_str:
            logger.error(
                "Database unavailable",
                extra={"error": str(e), "trace_id": trace_id, "latency_ms": latency_ms},
            )
            return JSONResponse(
                status_code=503,
                content={"detail": "Service unavailable: Database connection failed", "trace_id": trace_id},
            )

        import traceback
        err_trace = traceback.format_exc()
        logger.error(
            "Unhandled exception",
            extra={"error": str(e), "trace_id": trace_id, "traceback": err_trace, "latency_ms": latency_ms},
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "trace_id": trace_id},
        )
    finally:
        request_trace_id.reset(token)


# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(events.router)
app.include_router(metrics.router)
app.include_router(heatmap.router)
app.include_router(anomalies.router)
app.include_router(copilot.router)
app.include_router(event_stream.router)


@app.get("/", include_in_schema=False)
async def root():
    return {"service": "VisionRetail AI", "version": "1.0.0", "status": "running"}
