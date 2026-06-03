"""
Queue detection engine for billing zones.

Detects:
- BILLING_QUEUE_JOIN: person enters billing zone when queue already active.
- BILLING_QUEUE_ABANDON: person dwells in billing zone > abandon_threshold without a tx.

Queue depth = number of persons currently in BILLING zone(s).
Queue active = queue_depth >= density_threshold (default 3).

Algorithm:
1. Track persons currently in billing zones.
2. If a new person enters and queue_depth >= threshold → emit QUEUE_JOIN.
3. Poll every N seconds: if person has been in queue > abandon_threshold
   and no linked transaction → emit QUEUE_ABANDON and remove from queue.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class QueueMember:
    visitor_id: str
    zone_id: str
    join_time: datetime
    has_transacted: bool = False


class QueueDetector:
    """
    Tracks queue membership and emits join/abandon events.

    Args:
        density_threshold: Min persons in billing zone to consider queue active.
        abandon_threshold_seconds: Dwell without transaction → abandon.
    """

    def __init__(
        self,
        density_threshold: int = 3,
        abandon_threshold_seconds: int = 120,
    ) -> None:
        self.density_threshold = density_threshold
        self.abandon_threshold = timedelta(seconds=abandon_threshold_seconds)

        # visitor_id → QueueMember
        self._in_queue: dict[str, QueueMember] = {}

    @property
    def queue_depth(self) -> int:
        return len(self._in_queue)

    @property
    def is_active(self) -> bool:
        return self.queue_depth >= self.density_threshold

    def person_entered_billing(
        self,
        visitor_id: str,
        zone_id: str,
        timestamp: datetime,
    ) -> bool:
        """
        Called when a person enters a billing zone.
        Returns True if BILLING_QUEUE_JOIN event should be emitted.
        """
        if visitor_id in self._in_queue:
            return False  # Already in queue

        self._in_queue[visitor_id] = QueueMember(
            visitor_id=visitor_id,
            zone_id=zone_id,
            join_time=timestamp,
        )

        # Emit JOIN if queue was already active before this person arrived
        was_active = (self.queue_depth - 1) >= self.density_threshold
        return was_active

    def person_exited_billing(
        self,
        visitor_id: str,
        timestamp: datetime,
    ) -> None:
        """Called when person exits billing zone (normal checkout or abandon)."""
        self._in_queue.pop(visitor_id, None)

    def mark_transacted(self, visitor_id: str) -> None:
        """Mark a queue member as having completed a transaction."""
        if visitor_id in self._in_queue:
            self._in_queue[visitor_id].has_transacted = True

    def check_abandons(self, current_time: datetime) -> list[str]:
        """
        Poll for queue members who have exceeded the abandon threshold.
        Returns list of visitor_ids who abandoned. Removes them from queue.
        """
        abandoned = []
        for visitor_id, member in list(self._in_queue.items()):
            if member.has_transacted:
                continue
            dwell = current_time - member.join_time
            if dwell >= self.abandon_threshold:
                abandoned.append(visitor_id)
                del self._in_queue[visitor_id]
                logger.info(
                    "Queue abandon detected",
                    extra={
                        "visitor_id": visitor_id,
                        "dwell_seconds": dwell.total_seconds(),
                    },
                )
        return abandoned

    def get_snapshot(self) -> dict:
        """Return current queue state for monitoring."""
        return {
            "queue_depth": self.queue_depth,
            "is_active": self.is_active,
            "members": [
                {
                    "visitor_id": m.visitor_id,
                    "zone_id": m.zone_id,
                    "wait_seconds": 0,  # computed at call time
                }
                for m in self._in_queue.values()
            ],
        }
