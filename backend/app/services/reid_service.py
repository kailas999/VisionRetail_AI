"""
Re-ID Service — singleton wrapper around HybridReIDEngine.

Lifecycle:
  - Created at FastAPI startup (app.state.reid_service).
  - Resolves raw camera track_ids → stable cross-camera visitor_ids at ingest time.
  - Gracefully degrades: if torch/torchreid unavailable, passes visitor_id through unchanged.
  - Runs periodic GC to prune stale identities (>60 minutes unseen).

Usage in ingestion:
    resolved_vid = app.state.reid_service.resolve(
        raw_id=ev.visitor_id,
        camera_id=ev.camera_id,
        bbox=ev.metadata.get("bbox") if ev.metadata else None,
        timestamp=ev.timestamp,
    )

Fixes: CF-06
"""
from __future__ import annotations

import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class ReIDService:
    """
    Thread-safe singleton service wrapping HybridReIDEngine.

    Resolves raw camera track IDs → stable visitor_ids at ingest time.
    Gracefully degrades if torch/torchreid are unavailable.
    """

    def __init__(
        self,
        reid_threshold: float = 0.65,
        reentry_window_minutes: int = 30,
        gc_interval_minutes: int = 15,
    ) -> None:
        self._threshold = reid_threshold
        self._reentry_window = reentry_window_minutes
        self._gc_interval = gc_interval_minutes
        self._engine = None
        self._available = False
        self._gc_task: Optional[asyncio.Task] = None
        self._reid_calls = 0
        self._reid_merges = 0

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Initialise the Re-ID engine at startup. Non-blocking on failure."""
        try:
            from pipeline.reid_engine import HybridReIDEngine
            self._engine = HybridReIDEngine(
                reid_threshold=self._threshold,
                reentry_window_minutes=self._reentry_window,
            )
            self._available = True
            logger.info(
                "ReIDService started",
                extra={
                    "threshold": self._threshold,
                    "reentry_window_minutes": self._reentry_window,
                    "osnet_available": getattr(self._engine, "_osnet_available", False),
                },
            )
        except Exception as exc:
            self._available = False
            logger.warning(
                "ReIDService could not start — passing visitor_id through unchanged",
                extra={"error": str(exc)},
            )

        # Start background GC coroutine
        self._gc_task = asyncio.create_task(self._gc_loop())

    async def stop(self) -> None:
        """Cancel background GC task at shutdown."""
        if self._gc_task and not self._gc_task.done():
            self._gc_task.cancel()
            try:
                await self._gc_task
            except asyncio.CancelledError:
                pass
        logger.info(
            "ReIDService stopped",
            extra={
                "total_reid_calls": self._reid_calls,
                "total_merges": self._reid_merges,
            },
        )

    # ── Core API ─────────────────────────────────────────────────────────────

    def resolve(
        self,
        raw_id: str,
        camera_id: str,
        timestamp: datetime,
        bbox: Optional[dict] = None,
        embedding=None,
    ) -> tuple[str, bool]:
        """
        Resolve a raw camera track_id to a stable cross-camera visitor_id.

        Returns (visitor_id, is_reentry).

        If Re-ID engine unavailable, returns (raw_id, False) unchanged.
        The caller uses the returned visitor_id for all DB writes.
        """
        self._reid_calls += 1

        if not self._available or self._engine is None:
            return raw_id, False

        # Use track numeric part if raw_id is like "VIS_0042" → track_id = 42
        # Otherwise hash raw_id to a stable integer
        try:
            # Extract integer portion from IDs like "VIS_14_0003" or use hash
            parts = raw_id.split("_")
            track_id = int(parts[-1]) if parts[-1].isdigit() else abs(hash(raw_id)) % 100000
        except Exception:
            track_id = abs(hash(raw_id)) % 100000

        safe_bbox = bbox if bbox and all(k in bbox for k in ("x1", "y1", "x2", "y2")) \
                    else {"x1": 0, "y1": 0, "x2": 100, "y2": 200}

        try:
            visitor_id, is_new = self._engine.identify(
                track_id=track_id,
                camera_id=camera_id,
                embedding=embedding,
                bbox=safe_bbox,
                timestamp=timestamp,
            )
            is_reentry = self._engine.detect_reentry(visitor_id, timestamp)

            if not is_new:
                self._reid_merges += 1
                logger.debug(
                    "Re-ID merge",
                    extra={
                        "raw_id": raw_id,
                        "resolved_id": visitor_id,
                        "camera_id": camera_id,
                    },
                )

            return visitor_id, is_reentry

        except Exception as exc:
            logger.warning(
                "ReIDService.resolve failed — using raw_id",
                extra={"raw_id": raw_id, "error": str(exc)},
            )
            return raw_id, False

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def stats(self) -> dict:
        active = len(self._engine._identities) if self._engine else 0
        return {
            "available": self._available,
            "active_identities": active,
            "total_calls": self._reid_calls,
            "total_merges": self._reid_merges,
            "merge_rate": round(self._reid_merges / max(1, self._reid_calls), 4),
        }

    # ── Background GC ───────────────────────────────────────────────────────

    async def _gc_loop(self) -> None:
        """Periodically prune stale identities from the Re-ID engine."""
        interval = self._gc_interval * 60
        while True:
            try:
                await asyncio.sleep(interval)
                if self._engine is not None:
                    pruned = self._engine.gc_stale_identities(datetime.now(timezone.utc))
                    if pruned:
                        logger.debug("ReID GC", extra={"pruned": pruned})
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("ReID GC error", extra={"error": str(exc)})
