# PROMPT: "Write unit tests for a HybridReIDEngine that does cross-camera person re-identification using
# cosine similarity of OSNet embeddings + IoU-based bounding box trajectory matching. Test: new identity
# creation, same track same identity, high-IoU merge without embeddings, different locations = different persons,
# reentry detection (gap >5min within 30min window), no reentry within cooldown, no reentry beyond window,
# temporal score decay with increasing time gaps, GC of stale identities, and IoU calculation edge cases."
#
# CHANGES MADE:
# - Added 'self.engine._osnet_available = False' in setup to isolate trajectory-based matching (AI missed this).
# - test_iou_high_same_person_no_osnet: AI generated an OSNet embedding test, replaced with bbox-only to match unit scope.
# - Added test_gc_removes_stale_identities (AI missed GC testing entirely).
# - Removed test_embedding_similarity_threshold which required loading real OSNet model (not suitable for unit tests).
"""Unit tests for Hybrid Re-ID Engine."""
import math
from datetime import datetime, timezone, timedelta
import numpy as np
import pytest

from pipeline.reid_engine import HybridReIDEngine, PersonIdentity


def make_bbox(x1=100, y1=100, x2=200, y2=400):
    return {"x1": x1, "y1": y1, "x2": x2, "y2": y2}


def make_embedding(seed=42, dims=512):
    rng = np.random.RandomState(seed)
    emb = rng.randn(dims).astype(np.float32)
    return emb / np.linalg.norm(emb)


class TestHybridReIDEngine:
    def setup_method(self):
        self.engine = HybridReIDEngine(reid_threshold=0.65, reentry_window_minutes=30)
        self.engine._osnet_available = False  # Disable OSNet for unit tests

    def test_new_identity_created(self):
        ts = datetime.now(timezone.utc)
        vid, is_new = self.engine.identify(1, "CAM_01", None, make_bbox(), ts)
        assert is_new is True
        assert vid.startswith("VIS_")

    def test_same_track_same_identity(self):
        ts = datetime.now(timezone.utc)
        vid1, _ = self.engine.identify(1, "CAM_01", None, make_bbox(), ts)
        vid2, is_new = self.engine.identify(1, "CAM_01", None, make_bbox(), ts + timedelta(seconds=5))
        assert vid1 == vid2
        assert is_new is False

    def test_iou_high_same_person_no_osnet(self):
        """High IoU + close temporal → should merge without OSNet."""
        ts = datetime.now(timezone.utc)
        bbox = make_bbox(100, 100, 200, 400)
        vid1, _ = self.engine.identify(1, "CAM_01", None, bbox, ts)
        # Same bbox, 2 seconds later — high trajectory similarity
        vid2, is_new = self.engine.identify(99, "CAM_01", None, bbox, ts + timedelta(seconds=2))
        # Should merge (high IoU + temporal)
        assert vid1 == vid2

    def test_different_locations_different_persons(self):
        """Zero IoU + different tracks → different identities."""
        ts = datetime.now(timezone.utc)
        bbox1 = make_bbox(0, 0, 50, 100)
        bbox2 = make_bbox(900, 500, 1000, 700)
        vid1, _ = self.engine.identify(1, "CAM_01", None, bbox1, ts)
        vid2, _ = self.engine.identify(2, "CAM_01", None, bbox2, ts)
        assert vid1 != vid2

    def test_reentry_detection(self):
        """Person seen, gap > 5min, within 30min → reentry."""
        ts = datetime.now(timezone.utc)
        vid, _ = self.engine.identify(1, "CAM_01", None, make_bbox(), ts)
        # Simulate 10 minute gap
        is_reentry = self.engine.detect_reentry(vid, ts + timedelta(minutes=10))
        assert is_reentry is True

    def test_no_reentry_before_cooldown(self):
        """Gap < 5min → not reentry."""
        ts = datetime.now(timezone.utc)
        vid, _ = self.engine.identify(1, "CAM_01", None, make_bbox(), ts)
        is_reentry = self.engine.detect_reentry(vid, ts + timedelta(minutes=2))
        assert is_reentry is False

    def test_no_reentry_beyond_window(self):
        """Gap > 30min → beyond window, not reentry."""
        ts = datetime.now(timezone.utc)
        vid, _ = self.engine.identify(1, "CAM_01", None, make_bbox(), ts)
        is_reentry = self.engine.detect_reentry(vid, ts + timedelta(minutes=45))
        assert is_reentry is False

    def test_temporal_score_decay(self):
        """Temporal score should decrease as time gap increases."""
        ts = datetime.now(timezone.utc)
        identity = PersonIdentity(
            visitor_id="VIS_TEST",
            last_seen=ts,
            last_bbox=make_bbox(),
            last_camera="CAM_01",
        )

        score_2min = self.engine.compute_score(None, make_bbox(), ts + timedelta(minutes=2), "CAM_01", identity)
        score_15min = self.engine.compute_score(None, make_bbox(), ts + timedelta(minutes=15), "CAM_01", identity)
        score_29min = self.engine.compute_score(None, make_bbox(), ts + timedelta(minutes=29), "CAM_01", identity)

        assert score_2min > score_15min > score_29min

    def test_gc_removes_stale_identities(self):
        ts = datetime.now(timezone.utc)
        self.engine.identify(1, "CAM_01", None, make_bbox(), ts)
        assert len(self.engine._identities) == 1
        pruned = self.engine.gc_stale_identities(ts + timedelta(hours=2))
        assert pruned == 1
        assert len(self.engine._identities) == 0

    def test_iou_zero_non_overlapping(self):
        boxA = {"x1": 0, "y1": 0, "x2": 100, "y2": 100}
        boxB = {"x1": 200, "y1": 200, "x2": 300, "y2": 300}
        assert self.engine._iou(boxA, boxB) == 0.0

    def test_iou_perfect_overlap(self):
        box = {"x1": 0, "y1": 0, "x2": 100, "y2": 100}
        assert self.engine._iou(box, box) == 1.0
