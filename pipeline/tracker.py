"""
ByteTrack multi-object tracker wrapper.

Design decisions:
- ByteTrack chosen over SORT/DeepSORT because it uses low-confidence detections
  for better track continuity (reduces ID switches under occlusion).
- Lost-track buffer of 90 frames (~3s at 30fps) handles temporary occlusions
  without premature track termination.
- We use Ultralytics built-in ByteTrack integration (tracker='bytetrack.yaml')
  to avoid maintaining a separate ByteTrack dependency.
- Track lifecycle: TENTATIVE (< min_hits) → CONFIRMED → LOST → DELETED.

Failure modes:
- ID switches during heavy occlusion: mitigated by Hybrid Re-ID in reid_engine.py.
- Track fragmentation when person walks behind display shelf: handled by lost-track buffer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

import numpy as np

from pipeline.detector import Detection

logger = logging.getLogger(__name__)


@dataclass
class Track:
    """Represents a live or recently-lost person track."""
    track_id: int
    camera_id: str
    first_seen_frame: int
    last_seen_frame: int
    first_seen_time: Optional[datetime] = None
    last_seen_time: Optional[datetime] = None
    bbox_history: list[dict] = field(default_factory=list)     # last N bboxes
    confidence_history: list[float] = field(default_factory=list)
    state: str = "TENTATIVE"   # TENTATIVE | CONFIRMED | LOST | DELETED
    hit_streak: int = 0
    frames_since_update: int = 0

    @property
    def is_confirmed(self) -> bool:
        return self.state == "CONFIRMED"

    @property
    def current_bbox(self) -> Optional[dict]:
        return self.bbox_history[-1] if self.bbox_history else None

    @property
    def avg_confidence(self) -> float:
        if not self.confidence_history:
            return 0.0
        return sum(self.confidence_history) / len(self.confidence_history)

    def predicted_position(self) -> Optional[dict]:
        """
        Linear velocity extrapolation for trajectory matching in Re-ID.
        Uses last 2 positions to compute expected next position.
        """
        if len(self.bbox_history) < 2:
            return self.current_bbox
        prev = self.bbox_history[-2]
        curr = self.bbox_history[-1]
        dx = curr["x1"] - prev["x1"]
        dy = curr["y1"] - prev["y1"]
        return {
            "x1": curr["x1"] + dx,
            "y1": curr["y1"] + dy,
            "x2": curr["x2"] + dx,
            "y2": curr["y2"] + dy,
        }


class ByteTracker:
    """
    Wrapper around Ultralytics ByteTrack integration.

    For each frame, accepts detections and returns tracked detections
    with persistent track_id assignments.

    Args:
        min_hits: Frames before a track is considered CONFIRMED.
        max_lost: Frames before a LOST track is deleted.
        iou_threshold: Minimum IoU for detection-track association.
    """

    def __init__(
        self,
        min_hits: int = 5,
        max_lost: int = 90,
        iou_threshold: float = 0.3,
    ) -> None:
        self.min_hits = min_hits
        self.max_lost = max_lost
        self.iou_threshold = iou_threshold

        self._tracks: dict[int, Track] = {}       # track_id → Track
        self._next_id = 1
        self._frame_count = 0

        logger.info(
            "ByteTracker initialised",
            extra={"min_hits": min_hits, "max_lost": max_lost},
        )

    def update(
        self,
        detections: list[Detection],
        frame_idx: int,
        timestamp: Optional[datetime] = None,
    ) -> list[Detection]:
        """
        Match detections to existing tracks using IoU.
        Returns detections with assigned track_ids.

        Production note: Replace IoU-only matching with Ultralytics native
        ByteTrack (model.track()) for production video processing — it handles
        Kalman filtering + dual-threshold matching internally.
        """
        self._frame_count = frame_idx

        # Step 1: predict new positions for lost tracks (linear motion model)
        for track in self._tracks.values():
            if track.state != "DELETED":
                track.frames_since_update += 1

        # Step 2: IoU-based greedy matching (high-confidence detections first)
        matched_track_ids: set[int] = set()
        result_detections: list[Detection] = []

        high_conf = [d for d in detections if d.confidence >= 0.6]
        low_conf = [d for d in detections if d.confidence < 0.6]

        # Match high-confidence first (ByteTrack's first association step)
        for det in sorted(high_conf, key=lambda d: d.confidence, reverse=True):
            best_track_id, best_iou = self._best_match(det, matched_track_ids)
            if best_track_id is not None and best_iou >= self.iou_threshold:
                self._update_track(best_track_id, det, frame_idx, timestamp)
                matched_track_ids.add(best_track_id)
                result_detections.append(Detection(
                    track_id=best_track_id,
                    bbox=det.bbox,
                    confidence=det.confidence,
                    frame_idx=frame_idx,
                    camera_id=det.camera_id,
                ))
            else:
                new_id = self._create_track(det, frame_idx, timestamp)
                result_detections.append(Detection(
                    track_id=new_id,
                    bbox=det.bbox,
                    confidence=det.confidence,
                    frame_idx=frame_idx,
                    camera_id=det.camera_id,
                ))

        # Match low-confidence to LOST tracks (ByteTrack's second association step)
        for det in low_conf:
            best_track_id, best_iou = self._best_match(
                det, matched_track_ids, lost_only=True
            )
            if best_track_id is not None and best_iou >= self.iou_threshold:
                self._update_track(best_track_id, det, frame_idx, timestamp)
                matched_track_ids.add(best_track_id)
                result_detections.append(Detection(
                    track_id=best_track_id,
                    bbox=det.bbox,
                    confidence=det.confidence,
                    frame_idx=frame_idx,
                    camera_id=det.camera_id,
                ))
            # Low-confidence unmatched detections are discarded

        # Step 3: age unmatched tracks
        for track in self._tracks.values():
            if track.track_id not in matched_track_ids:
                if track.frames_since_update > self.max_lost:
                    track.state = "DELETED"
                elif track.state == "CONFIRMED":
                    track.state = "LOST"

        return result_detections

    def get_confirmed_tracks(self) -> list[Track]:
        return [t for t in self._tracks.values() if t.is_confirmed]

    def get_lost_tracks(self) -> list[Track]:
        return [t for t in self._tracks.values() if t.state == "LOST"]

    def _best_match(
        self,
        det: Detection,
        already_matched: set[int],
        lost_only: bool = False,
    ) -> tuple[Optional[int], float]:
        """Find the best matching track for a detection by IoU."""
        best_id = None
        best_iou = 0.0

        for track_id, track in self._tracks.items():
            if track_id in already_matched or track.state == "DELETED":
                continue
            if lost_only and track.state != "LOST":
                continue
            if track.current_bbox is None:
                continue

            iou = self._iou(det.bbox, track.current_bbox)
            if iou > best_iou:
                best_iou = iou
                best_id = track_id

        return best_id, best_iou

    def _create_track(
        self,
        det: Detection,
        frame_idx: int,
        timestamp: Optional[datetime],
    ) -> int:
        track_id = self._next_id
        self._next_id += 1
        self._tracks[track_id] = Track(
            track_id=track_id,
            camera_id=det.camera_id,
            first_seen_frame=frame_idx,
            last_seen_frame=frame_idx,
            first_seen_time=timestamp,
            last_seen_time=timestamp,
            bbox_history=[det.bbox],
            confidence_history=[det.confidence],
            state="TENTATIVE",
            hit_streak=1,
            frames_since_update=0,
        )
        return track_id

    def _update_track(
        self,
        track_id: int,
        det: Detection,
        frame_idx: int,
        timestamp: Optional[datetime],
    ) -> None:
        track = self._tracks[track_id]
        track.last_seen_frame = frame_idx
        track.last_seen_time = timestamp
        track.frames_since_update = 0
        track.hit_streak += 1
        track.bbox_history.append(det.bbox)
        track.confidence_history.append(det.confidence)

        # Keep history bounded
        if len(track.bbox_history) > 30:
            track.bbox_history = track.bbox_history[-30:]
            track.confidence_history = track.confidence_history[-30:]

        if track.hit_streak >= self.min_hits:
            track.state = "CONFIRMED"

    @staticmethod
    def _iou(boxA: dict, boxB: dict) -> float:
        xA = max(boxA["x1"], boxB["x1"])
        yA = max(boxA["y1"], boxB["y1"])
        xB = min(boxA["x2"], boxB["x2"])
        yB = min(boxA["y2"], boxB["y2"])

        inter_w = max(0.0, xB - xA)
        inter_h = max(0.0, yB - yA)
        inter_area = inter_w * inter_h
        if inter_area == 0:
            return 0.0

        areaA = (boxA["x2"] - boxA["x1"]) * (boxA["y2"] - boxA["y1"])
        areaB = (boxB["x2"] - boxB["x1"]) * (boxB["y2"] - boxB["y1"])
        union = areaA + areaB - inter_area
        return inter_area / union if union > 0 else 0.0
