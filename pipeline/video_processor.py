"""
Video Processor — orchestrates the full CV pipeline for one video file.

Flow per frame:
  YOLOv8m detect → ByteTrack track → Hybrid Re-ID → Zone classify →
  Staff detect → Queue detect → Event generate → Collect events

Handles:
- Group entry (multiple persons in same frame → all tracked independently)
- Re-entry (Re-ID detects known visitor after gap)
- Partial occlusion (ByteTrack's lost-track buffer maintains ID)
- Empty periods (no detections → no events, metrics updated with 0)
- Staff filtering (staff events marked is_staff=True)
- Camera overlap (Re-ID cross-camera identity merging)

Usage:
    python pipeline/video_processor.py \
        --video data/videos/camera_01.mp4 \
        --store STORE_BLR_002 \
        --layout data/store_layout.json \
        --output events.jsonl
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# Pipeline modules
from pipeline.detector import PersonDetector, Detection
from pipeline.tracker import ByteTracker, Track
from pipeline.reid_engine import HybridReIDEngine
from pipeline.staff_detector import StaffDetector
from pipeline.zone_classifier import ZoneClassifier, ZoneDefinition
from pipeline.queue_detector import QueueDetector
from pipeline.event_generator import EventGenerator, GeneratedEvent

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────
BATCH_SIZE = 4
DWELL_EMIT_INTERVAL_SECONDS = 30   # Emit ZONE_DWELL every N seconds of continuous dwell
GC_INTERVAL_FRAMES = 300           # Run Re-ID GC every N frames


class VideoProcessor:
    """
    Full pipeline orchestrator for a single camera feed.

    Args:
        store_id: Store identifier.
        camera_id: Camera identifier.
        layout_path: Path to store_layout.json.
        video_start_time: Wall-clock time of video start (for timestamp generation).
        reid_threshold: Re-ID merge threshold.
        reentry_window_minutes: Max gap for re-entry detection.
    """

    def __init__(
        self,
        store_id: str,
        camera_id: str,
        layout_path: str,
        video_start_time: Optional[datetime] = None,
        yolo_model: str = "yolov8m.pt",
        yolo_confidence: float = 0.35,
        reid_threshold: float = 0.65,
        reentry_window_minutes: int = 30,
        staff_threshold: float = 0.75,
        queue_density_threshold: int = 1,
        queue_abandon_seconds: int = 120,
    ) -> None:
        self.store_id = store_id
        self.camera_id = camera_id
        self.video_start_time = video_start_time or datetime.now(timezone.utc)

        # Initialise pipeline components
        self.detector = PersonDetector(
            model_path=yolo_model,
            confidence=yolo_confidence,
        )
        self.tracker = ByteTracker(min_hits=5, max_lost=90)
        self.reid_engine = HybridReIDEngine(
            reid_threshold=reid_threshold,
            reentry_window_minutes=reentry_window_minutes,
        )
        self.zone_classifier = ZoneClassifier.from_layout_file(layout_path, store_id)
        self.staff_detector = StaffDetector(
            staff_threshold=staff_threshold,
            total_zones=len(self.zone_classifier.get_all_zones()),
        )
        self.queue_detector = QueueDetector(
            density_threshold=queue_density_threshold,
            abandon_threshold_seconds=queue_abandon_seconds,
        )
        self.event_generator = EventGenerator(store_id=store_id, camera_id=camera_id)

        # Per-track state
        self._current_zones: dict[str, Optional[str]] = {}     # visitor_id → zone_id
        self._zone_entry_times: dict[str, dict[str, datetime]] = {}  # visitor_id → {zone_id: entry_time}
        self._last_dwell_emit: dict[str, dict[str, datetime]] = {}
        self._active_visitors: set[str] = set()
        self._visitor_entry_times: dict[str, datetime] = {}

        self._all_events: list[GeneratedEvent] = []
        logger.info("VideoProcessor initialised", extra={"store": store_id, "camera": camera_id})

    def process(self, video_path: str):
        """Process full video file. Yields lists of generated events."""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        logger.info(
            "Processing video",
            extra={"path": video_path, "fps": fps, "total_frames": total_frames},
        )

        frame_buffer: list[np.ndarray] = []
        frame_idx_buffer: list[int] = []
        frame_idx = 0

        TARGET_FPS = 5.0
        frame_skip_interval = max(1, int(fps / TARGET_FPS))

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                # Frame skipping
                if frame_idx % frame_skip_interval != 0:
                    frame_idx += 1
                    continue

                # Resolution Downscaling
                h, w = frame.shape[:2]
                if w > 640:
                    scale = 640 / w
                    frame = cv2.resize(frame, (640, int(h * scale)))

                frame_buffer.append(frame)
                frame_idx_buffer.append(frame_idx)

                if len(frame_buffer) == BATCH_SIZE:
                    self._process_batch(frame_buffer, frame_idx_buffer, fps)
                    frame_buffer = []
                    frame_idx_buffer = []

                    if self._all_events:
                        yield self._all_events
                        self._all_events = []

                frame_idx += 1

                # GC
                if frame_idx % GC_INTERVAL_FRAMES == 0:
                    current_ts = self._frame_to_timestamp(frame_idx, fps)
                    self.reid_engine.gc_stale_identities(current_ts)

            # Process remaining frames
            if frame_buffer:
                self._process_batch(frame_buffer, frame_idx_buffer, fps)
                if self._all_events:
                    yield self._all_events
                    self._all_events = []

        finally:
            cap.release()

        # Emit EXIT events for all visitors still in store at video end
        end_ts = self._frame_to_timestamp(frame_idx, fps)
        self._emit_exit_for_all_active(end_ts)
        
        if self._all_events:
            yield self._all_events
            self._all_events = []

        logger.info("Video processing complete")

    def _process_batch(
        self, frames: list[np.ndarray], frame_indices: list[int], fps: float
    ) -> None:
        """Process a batch of frames through the full pipeline."""
        all_detections = self.detector.detect_batch(frames, frame_indices, self.camera_id)

        for i, frame_detections in enumerate(all_detections):
            frame_idx = frame_indices[i]
            timestamp = self._frame_to_timestamp(frame_idx, fps)
            frame = frames[i]

            # Calibrate confidence
            calibrated = self.detector.calibrate_confidence(frame_detections)

            # Track
            tracked = self.tracker.update(calibrated, frame_idx, timestamp)

            # Re-ID + zone + events per detected person
            self._process_frame_detections(tracked, frame, timestamp)

            # Check queue abandons
            abandoned_visitors = self.queue_detector.check_abandons(timestamp)
            for vis_id in abandoned_visitors:
                zone_id = self._current_zones.get(vis_id)
                dwell = (timestamp - self._zone_entry_times.get(vis_id, {}).get(zone_id or "", timestamp)).total_seconds()
                event = self.event_generator.emit_queue_abandon(
                    visitor_id=vis_id,
                    zone_id=zone_id or "BILLING",
                    timestamp=timestamp,
                    dwell_seconds=dwell,
                    is_staff=False,
                )
                if event:
                    self._all_events.append(event)

    def _process_frame_detections(
        self,
        detections: list[Detection],
        frame: np.ndarray,
        timestamp: datetime,
    ) -> None:
        """Per-frame: Re-ID, zone classification, event generation."""
        for det in detections:
            if det.track_id is None:
                continue

            # Extract crop for OSNet embedding
            bbox = det.bbox
            crop = self._extract_crop(frame, bbox)
            embedding = self.reid_engine.extract_embedding(crop) if crop is not None else None

            # Re-ID: get stable visitor_id
            visitor_id, is_new = self.reid_engine.identify(
                track_id=det.track_id,
                camera_id=det.camera_id,
                embedding=embedding,
                bbox=bbox,
                timestamp=timestamp,
            )

            # Staff classification (update signal on every observation)
            current_zone = self._current_zones.get(visitor_id)
            self.staff_detector.update(
                visitor_id=visitor_id,
                timestamp=timestamp,
                zone_id=current_zone,
                dwell_delta_seconds=1.0 / 25.0,  # approximate per-frame dwell
            )
            is_staff, staff_score = self.staff_detector.classify(visitor_id)

            # Re-entry detection
            is_reentry = self.reid_engine.detect_reentry(visitor_id, timestamp)

            # Zone classification
            zone = self.zone_classifier.classify_bbox(bbox)
            zone_id = zone.zone_id if zone else None
            zone_type = zone.zone_type if zone else None

            # ── Event emission ──────────────────────────────────────────────

            # ENTRY / REENTRY
            if visitor_id not in self._active_visitors:
                self._active_visitors.add(visitor_id)
                self._visitor_entry_times[visitor_id] = timestamp

                if is_reentry:
                    ev = self.event_generator.emit_reentry(
                        visitor_id=visitor_id,
                        timestamp=timestamp,
                        detection_confidence=det.confidence,
                        is_staff=is_staff,
                        bbox=bbox,
                    )
                else:
                    ev = self.event_generator.emit_entry(
                        visitor_id=visitor_id,
                        timestamp=timestamp,
                        detection_confidence=det.confidence,
                        is_staff=is_staff,
                        bbox=bbox,
                    )
                if ev:
                    self._all_events.append(ev)

            # ZONE transitions
            prev_zone_id = self._current_zones.get(visitor_id)
            if zone_id != prev_zone_id:
                # ZONE_EXIT from previous zone
                if prev_zone_id is not None:
                    entry_time = self._zone_entry_times.get(visitor_id, {}).get(prev_zone_id)
                    dwell = (timestamp - entry_time).total_seconds() if entry_time else 0.0

                    ev = self.event_generator.emit_zone_exit(
                        visitor_id=visitor_id,
                        zone_id=prev_zone_id,
                        timestamp=timestamp,
                        detection_confidence=det.confidence,
                        is_staff=is_staff,
                        bbox=bbox,
                    )
                    if ev:
                        self._all_events.append(ev)

                    # ZONE_DWELL summary on exit
                    if dwell > 5:
                        ev = self.event_generator.emit_zone_dwell(
                            visitor_id=visitor_id,
                            zone_id=prev_zone_id,
                            timestamp=timestamp,
                            dwell_seconds=dwell,
                            is_staff=is_staff,
                            bbox=bbox,
                        )
                        if ev:
                            self._all_events.append(ev)

                    # Billing exit
                    if prev_zone_id in [z.zone_id for z in self.zone_classifier.get_billing_zones()]:
                        self.queue_detector.person_exited_billing(visitor_id, timestamp)
                        ev = self.event_generator.emit(
                            visitor_id=visitor_id,
                            event_type="PURCHASE",
                            timestamp=timestamp,
                            zone_id=prev_zone_id,
                            detection_confidence=det.confidence,
                            is_staff=is_staff,
                            bbox=bbox,
                        )
                        if ev:
                            self._all_events.append(ev)

                # ZONE_ENTER for new zone
                if zone_id is not None:
                    if visitor_id not in self._zone_entry_times:
                        self._zone_entry_times[visitor_id] = {}
                    self._zone_entry_times[visitor_id][zone_id] = timestamp

                    ev = self.event_generator.emit_zone_enter(
                        visitor_id=visitor_id,
                        zone_id=zone_id,
                        timestamp=timestamp,
                        detection_confidence=det.confidence,
                        is_staff=is_staff,
                        bbox=bbox,
                    )
                    if ev:
                        self._all_events.append(ev)

                    # Queue join detection
                    if zone_type == "BILLING":
                        should_emit_join = self.queue_detector.person_entered_billing(
                            visitor_id, zone_id, timestamp
                        )
                        if should_emit_join:
                            ev = self.event_generator.emit_queue_join(
                                visitor_id=visitor_id,
                                zone_id=zone_id,
                                timestamp=timestamp,
                                queue_depth=self.queue_detector.queue_depth,
                                is_staff=is_staff,
                                bbox=bbox,
                            )
                            if ev:
                                self._all_events.append(ev)

                self._current_zones[visitor_id] = zone_id

    def _emit_exit_for_all_active(self, timestamp: datetime) -> None:
        """Emit EXIT events for all visitors who didn't explicitly exit."""
        for visitor_id in list(self._active_visitors):
            ev = self.event_generator.emit_exit(
                visitor_id=visitor_id,
                timestamp=timestamp,
                detection_confidence=0.8,
                is_staff=self.staff_detector.classify(visitor_id)[0],
                extra_metadata={"reason": "video_end"},
            )
            if ev:
                self._all_events.append(ev)

    def _frame_to_timestamp(self, frame_idx: int, fps: float) -> datetime:
        offset_seconds = frame_idx / fps
        return self.video_start_time + timedelta(seconds=offset_seconds)

    @staticmethod
    def _extract_crop(
        frame: np.ndarray, bbox: dict, padding: int = 10
    ) -> Optional[np.ndarray]:
        """Extract person crop from frame with padding."""
        h, w = frame.shape[:2]
        x1 = max(0, int(bbox["x1"]) - padding)
        y1 = max(0, int(bbox["y1"]) - padding)
        x2 = min(w, int(bbox["x2"]) + padding)
        y2 = min(h, int(bbox["y2"]) + padding)
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2]


def main() -> None:
    parser = argparse.ArgumentParser(description="VisionRetail AI — Video Processor")
    parser.add_argument("--video", required=True, help="Path to video file")
    parser.add_argument("--store", required=True, help="Store ID")
    parser.add_argument("--camera", default="CAM_01", help="Camera ID")
    parser.add_argument("--layout", default="data/store_layout.json", help="Layout JSON path")
    parser.add_argument("--output", default="events.jsonl", help="Output JSONL path")
    parser.add_argument("--start-time", default=None, help="Video start time ISO8601")
    parser.add_argument("--api-url", default="http://localhost:8000", help="FastAPI URL for ingestion")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    start_time = (
        datetime.fromisoformat(args.start_time)
        if args.start_time
        else datetime.now(timezone.utc)
    )

    processor = VideoProcessor(
        store_id=args.store,
        camera_id=args.camera,
        layout_path=args.layout,
        video_start_time=start_time,
    )

    out_path = Path(args.output)
    logger.info(f"Streaming events to {out_path} and {args.api_url}")
    total_events = 0

    if args.api_url:
        import httpx

    with open(out_path, "w") as f:
        for events_batch in processor.process(args.video):
            if not events_batch:
                continue
                
            total_events += len(events_batch)
            payload_events = []
            
            for ev in events_batch:
                record = {
                    "event_id": str(ev.event_id),
                    "store_id": ev.store_id,
                    "camera_id": ev.camera_id,
                    "visitor_id": ev.visitor_id,
                    "event_type": ev.event_type,
                    "timestamp": ev.timestamp.isoformat(),
                    "zone_id": ev.zone_id,
                    "dwell_ms": ev.dwell_ms,
                    "is_staff": ev.is_staff,
                    "confidence": ev.confidence,
                    "metadata": ev.metadata,
                }
                f.write(json.dumps(record) + "\n")
                payload_events.append(record)
                
            f.flush()

            if args.api_url:
                payload = {"events": payload_events}
                try:
                    resp = httpx.post(f"{args.api_url}/events/ingest", json=payload, timeout=30)
                    resp.raise_for_status()
                    logger.info(f"Ingested batch of {len(payload_events)} events: {resp.json()}")
                except Exception as e:
                    logger.error(f"Ingestion failed: {e}")

    logger.info(f"Total events generated and streamed: {total_events}")

if __name__ == "__main__":
    main()
