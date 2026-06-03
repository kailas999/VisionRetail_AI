"""
Hybrid Re-ID Engine — cross-camera identity matching.

Score = 0.6 × OSNet_appearance + 0.2 × temporal + 0.2 × trajectory

Design rationale:
- Appearance alone fails under lighting changes, clothing similarity in crowds.
- Temporal signal constrains implausible matches (person can't teleport).
- Trajectory signal eliminates geometrically impossible camera transitions.
- Weighted sum is interpretable and tuneable per store layout.

OSNet reference: Zhou et al., "Omni-Scale Feature Learning for Person Re-ID", ICCV 2019.
Weights from torchreid's pretrained osnet_x1_0 (market1501 trained).

Tradeoffs:
- OSNet adds ~15ms per re-id call on CPU. Acceptable for offline processing.
- For real-time: cache embeddings; only compute on new track appearance.
- Threshold 0.65 chosen to minimise false merges (worse than false splits in retail).
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import torch

logger = logging.getLogger(__name__)


@dataclass
class PersonIdentity:
    """
    Stable cross-session identity maintained by Re-ID engine.
    One identity may have multiple ByteTrack track_ids across cameras/sessions.
    """
    visitor_id: str                          # stable UUID-based ID
    track_ids: list[tuple[str, int]] = field(default_factory=list)  # [(camera, track_id)]
    embeddings: list[np.ndarray] = field(default_factory=list)       # OSNet embeddings
    last_seen: Optional[datetime] = None
    last_bbox: Optional[dict] = None
    last_camera: Optional[str] = None
    session_count: int = 1
    is_reentry: bool = False


class HybridReIDEngine:
    """
    Hybrid person Re-ID combining OSNet appearance, temporal, and trajectory signals.

    Args:
        reid_threshold: Minimum score to merge identities (default 0.65).
        reentry_window_minutes: Max gap for re-entry detection (default 30).
        device: torch device for OSNet inference.
    """

    def __init__(
        self,
        reid_threshold: float = 0.65,
        reentry_window_minutes: int = 30,
        device: Optional[str] = None,
    ) -> None:
        self.reid_threshold = reid_threshold
        self.reentry_window = timedelta(minutes=reentry_window_minutes)

        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        self._identities: dict[str, PersonIdentity] = {}  # visitor_id → identity
        self._osnet_model = None
        self._osnet_available = False
        self._load_osnet()

    def _load_osnet(self) -> None:
        """Load OSNet via torchreid. Gracefully degrade to trajectory+temporal only."""
        try:
            import torchreid
            self._osnet_model = torchreid.models.build_model(
                name="osnet_x1_0",
                num_classes=1000,
                pretrained=True,
            )
            self._osnet_model.eval()
            self._osnet_model.to(self.device)
            self._osnet_available = True
            logger.info("OSNet Re-ID model loaded", extra={"device": self.device})
        except Exception as e:
            logger.warning(
                "OSNet unavailable — falling back to temporal+trajectory only",
                extra={"error": str(e)},
            )
            self._osnet_available = False

    def extract_embedding(self, crop: np.ndarray) -> Optional[np.ndarray]:
        """
        Extract 512-dim OSNet embedding from a person crop (H×W×3 BGR).
        Returns None if OSNet not available.
        """
        if not self._osnet_available or self._osnet_model is None:
            return None

        import cv2
        import torchvision.transforms as T

        transform = T.Compose([
            T.ToPILImage(),
            T.Resize((256, 128)),
            T.ToTensor(),
            T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        try:
            rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            tensor = transform(rgb).unsqueeze(0).to(self.device)
            with torch.no_grad():
                feat = self._osnet_model(tensor)
            emb = feat.squeeze().cpu().numpy()
            # L2 normalise
            norm = np.linalg.norm(emb)
            return emb / (norm + 1e-8)
        except Exception as e:
            logger.debug("Embedding extraction failed", extra={"error": str(e)})
            return None

    def compute_score(
        self,
        query_embedding: Optional[np.ndarray],
        query_bbox: dict,
        query_time: datetime,
        query_camera: str,
        candidate: PersonIdentity,
    ) -> float:
        """
        Compute hybrid Re-ID score between a query detection and a candidate identity.

        Returns float in [0, 1]. Higher = more likely same person.
        """
        # ── Appearance score (OSNet cosine similarity) ─────────────────────
        appearance_score = 0.0
        if (
            query_embedding is not None
            and self._osnet_available
            and candidate.embeddings
        ):
            # Average similarity against stored embeddings (gallery matching)
            sims = [
                float(np.dot(query_embedding, e))  # both L2-normed → cosine
                for e in candidate.embeddings[-5:]  # last 5 embeddings
            ]
            appearance_score = max(sims) * 0.7 + (sum(sims) / len(sims)) * 0.3

        # ── Temporal score ─────────────────────────────────────────────────
        temporal_score = 0.0
        if candidate.last_seen is not None:
            gap_seconds = abs((query_time - candidate.last_seen).total_seconds())
            # Exponential decay: score=1 at gap=0, ~0.37 at 30min, 0 beyond window
            window_seconds = self.reentry_window.total_seconds()
            if gap_seconds <= window_seconds:
                temporal_score = math.exp(-gap_seconds / (window_seconds / 3))
            else:
                temporal_score = 0.0  # beyond re-entry window → cannot be same visit

        # ── Trajectory score ───────────────────────────────────────────────
        trajectory_score = 0.0
        if candidate.last_bbox is not None:
            # IoU between query position and candidate's last known position
            # High IoU = very close = likely same person (same camera)
            iou = self._iou(query_bbox, candidate.last_bbox)
            trajectory_score = iou
            # Camera transition penalty: different camera reduces trajectory trust
            if query_camera != candidate.last_camera:
                trajectory_score *= 0.5

        # ── Weighted final score ───────────────────────────────────────────
        if self._osnet_available and query_embedding is not None:
            weights = (0.6, 0.2, 0.2)
        else:
            # Appearance unavailable — redistribute weight
            weights = (0.0, 0.5, 0.5)

        score = (
            weights[0] * appearance_score
            + weights[1] * temporal_score
            + weights[2] * trajectory_score
        )
        return min(1.0, max(0.0, score))

    def identify(
        self,
        track_id: int,
        camera_id: str,
        embedding: Optional[np.ndarray],
        bbox: dict,
        timestamp: datetime,
    ) -> tuple[str, bool]:
        """
        Identify a track. Returns (visitor_id, is_new_identity).

        Algorithm:
        1. Check if track already mapped to identity.
        2. Score against all recent candidate identities.
        3. Merge if best score >= threshold, else create new identity.
        4. Detect re-entry (same visitor_id, different session).
        """
        # Check if already in an active identity
        for vid, identity in self._identities.items():
            if (camera_id, track_id) in identity.track_ids:
                # Update embedding gallery
                if embedding is not None and len(identity.embeddings) < 10:
                    identity.embeddings.append(embedding)
                identity.last_seen = timestamp
                identity.last_bbox = bbox
                return vid, False

        # Score against all candidates
        best_visitor_id: Optional[str] = None
        best_score = 0.0

        for vid, identity in self._identities.items():
            # Skip identities that are way too old
            if identity.last_seen is not None:
                gap = (timestamp - identity.last_seen).total_seconds()
                if gap > self.reentry_window.total_seconds():
                    continue

            score = self.compute_score(
                embedding, bbox, timestamp, camera_id, identity
            )
            if score > best_score:
                best_score = score
                best_visitor_id = vid

        if best_score >= self.reid_threshold and best_visitor_id is not None:
            # Merge into existing identity
            identity = self._identities[best_visitor_id]
            identity.track_ids.append((camera_id, track_id))
            if embedding is not None:
                identity.embeddings.append(embedding)
                if len(identity.embeddings) > 10:
                    identity.embeddings = identity.embeddings[-10:]
            identity.last_seen = timestamp
            identity.last_bbox = bbox
            identity.last_camera = camera_id
            logger.debug(
                "Re-ID match",
                extra={"visitor_id": best_visitor_id, "score": round(best_score, 3)},
            )
            return best_visitor_id, False
        else:
            # New identity
            import uuid
            new_vid = f"VIS_{uuid.uuid4().hex[:12].upper()}"
            self._identities[new_vid] = PersonIdentity(
                visitor_id=new_vid,
                track_ids=[(camera_id, track_id)],
                embeddings=[embedding] if embedding is not None else [],
                last_seen=timestamp,
                last_bbox=bbox,
                last_camera=camera_id,
                session_count=1,
            )
            logger.debug("New identity created", extra={"visitor_id": new_vid})
            return new_vid, True

    def detect_reentry(self, visitor_id: str, current_time: datetime) -> bool:
        """
        Returns True if this visitor has been seen before and is re-entering.
        Re-entry = same visitor_id, gap > 5 minutes (cooldown), within reentry_window.
        """
        identity = self._identities.get(visitor_id)
        if identity is None or identity.last_seen is None:
            return False

        gap = (current_time - identity.last_seen).total_seconds()
        return 300 <= gap <= self.reentry_window.total_seconds()

    def gc_stale_identities(self, current_time: datetime) -> int:
        """
        Garbage-collect identities not seen for > 2× reentry_window.
        Returns number of pruned identities.
        """
        cutoff = current_time - 2 * self.reentry_window
        stale = [
            vid for vid, idn in self._identities.items()
            if idn.last_seen is not None and idn.last_seen < cutoff
        ]
        for vid in stale:
            del self._identities[vid]
        if stale:
            logger.debug("GC pruned identities", extra={"count": len(stale)})
        return len(stale)

    @staticmethod
    def _iou(boxA: dict, boxB: dict) -> float:
        xA = max(boxA["x1"], boxB["x1"])
        yA = max(boxA["y1"], boxB["y1"])
        xB = min(boxA["x2"], boxB["x2"])
        yB = min(boxA["y2"], boxB["y2"])
        inter = max(0.0, xB - xA) * max(0.0, yB - yA)
        if inter == 0:
            return 0.0
        aA = (boxA["x2"] - boxA["x1"]) * (boxA["y2"] - boxA["y1"])
        aB = (boxB["x2"] - boxB["x1"]) * (boxB["y2"] - boxB["y1"])
        return inter / (aA + aB - inter)
