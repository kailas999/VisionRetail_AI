"""
Staff detection engine — hybrid multi-signal approach.

Why NOT colour-only heuristics:
- Staff uniforms vary by store, season, promotional events.
- Customers wearing similar colours would be misclassified.
- Colour is brittle under different lighting conditions.

Hybrid signals:
1. Presence duration: staff stay for full shift (8h+), customers < 60min.
2. Zone coverage: staff cover multiple zones repeatedly.
3. Repeat appearances: staff re-appear daily.
4. Opening/closing pattern: present at store open/close times.

Score = Σ(weight_i × signal_i), threshold 0.75 → is_staff = True

Design tradeoff:
- Conservative threshold (0.75) to avoid misclassifying customers as staff.
- False negative (staff counted as customer) is safer than false positive.
- For ground-truth validation: allow store operators to label staff IDs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Weights for staff scoring ─────────────────────────────────────────────
WEIGHT_DURATION = 0.35
WEIGHT_ZONE_COVERAGE = 0.25
WEIGHT_REPEAT = 0.25
WEIGHT_OPEN_CLOSE = 0.15

STAFF_THRESHOLD = 0.75


@dataclass
class VisitorProfile:
    """Accumulated signals per visitor_id for staff detection."""
    visitor_id: str
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    total_dwell_seconds: float = 0.0
    zones_visited: set = field(default_factory=set)
    visit_dates: set = field(default_factory=set)       # date strings
    seen_at_open: bool = False       # present within 30min of store open
    seen_at_close: bool = False      # present within 30min of store close
    staff_score: float = 0.0
    is_staff: bool = False


class StaffDetector:
    """
    Hybrid staff detection using dwell, zone coverage, repeat, and schedule signals.

    Args:
        staff_threshold: Minimum score to classify as staff.
        store_open_hour: Hour (0-23) when store opens.
        store_close_hour: Hour (0-23) when store closes.
        min_staff_dwell_hours: Minimum dwell time for definitive staff signal.
    """

    def __init__(
        self,
        staff_threshold: float = STAFF_THRESHOLD,
        store_open_hour: int = 9,
        store_close_hour: int = 21,
        min_staff_dwell_hours: float = 3.0,
        total_zones: int = 6,
    ) -> None:
        self.staff_threshold = staff_threshold
        self.store_open_hour = store_open_hour
        self.store_close_hour = store_close_hour
        self.min_staff_dwell_hours = min_staff_dwell_hours
        self.total_zones = max(1, total_zones)

        self._profiles: dict[str, VisitorProfile] = {}

    def update(
        self,
        visitor_id: str,
        timestamp: datetime,
        zone_id: Optional[str] = None,
        dwell_delta_seconds: float = 0.0,
    ) -> None:
        """Update profile signals for visitor_id."""
        if visitor_id not in self._profiles:
            self._profiles[visitor_id] = VisitorProfile(visitor_id=visitor_id)

        p = self._profiles[visitor_id]

        if p.first_seen is None:
            p.first_seen = timestamp
        p.last_seen = timestamp
        p.total_dwell_seconds += dwell_delta_seconds

        if zone_id:
            p.zones_visited.add(zone_id)

        p.visit_dates.add(timestamp.date().isoformat())

        # Opening / closing proximity
        hour = timestamp.hour
        if abs(hour - self.store_open_hour) <= 1:
            p.seen_at_open = True
        if abs(hour - self.store_close_hour) <= 1:
            p.seen_at_close = True

    def score(self, visitor_id: str) -> float:
        """Compute current staff confidence score for a visitor."""
        p = self._profiles.get(visitor_id)
        if p is None:
            return 0.0

        # Signal 1: Duration score
        dwell_hours = p.total_dwell_seconds / 3600.0
        duration_score = min(1.0, dwell_hours / self.min_staff_dwell_hours)

        # Signal 2: Zone coverage score
        coverage_score = min(1.0, len(p.zones_visited) / self.total_zones)

        # Signal 3: Repeat appearances (unique days seen)
        repeat_score = min(1.0, (len(p.visit_dates) - 1) / 5.0)

        # Signal 4: Open/close pattern
        open_close_score = 0.0
        if p.seen_at_open:
            open_close_score += 0.5
        if p.seen_at_close:
            open_close_score += 0.5

        staff_score = (
            WEIGHT_DURATION * duration_score
            + WEIGHT_ZONE_COVERAGE * coverage_score
            + WEIGHT_REPEAT * repeat_score
            + WEIGHT_OPEN_CLOSE * open_close_score
        )

        return round(staff_score, 4)

    def classify(self, visitor_id: str) -> tuple[bool, float]:
        """
        Returns (is_staff, confidence_score).
        Updates the stored profile.
        """
        s = self.score(visitor_id)
        p = self._profiles.get(visitor_id)
        if p:
            p.staff_score = s
            p.is_staff = s >= self.staff_threshold

        is_staff = s >= self.staff_threshold
        if is_staff:
            logger.info("Staff detected", extra={"visitor_id": visitor_id, "score": s})

        return is_staff, s

    def get_known_staff(self) -> list[str]:
        """Return all visitor_ids currently classified as staff."""
        return [
            vid for vid, p in self._profiles.items()
            if p.is_staff
        ]
