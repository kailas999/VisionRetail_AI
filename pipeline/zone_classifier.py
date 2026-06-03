"""
Zone classifier using Shapely point-in-polygon matching.

Design:
- Each zone has a polygon defined in store_layout.json as [[x,y], ...] pixel coords.
- Person position = bottom-centre of bounding box (foot position, not head).
- Zones sorted by priority (higher first) to resolve overlaps.
- BILLING zone triggers queue detection downstream.

Edge cases handled:
- Person at zone boundary: Shapely boundary is treated as interior.
- Multiple overlapping zones: highest-priority zone wins.
- No zone match: returns None (open floor area).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Optional

from shapely.geometry import Point, Polygon

logger = logging.getLogger(__name__)


@dataclass
class ZoneDefinition:
    zone_id: str
    name: str
    zone_type: str         # ENTRY, EXIT, DISPLAY, BILLING, AISLE, FITTING_ROOM
    polygon: list[list[float]]   # [[x,y], ...]
    priority: int = 0
    _shapely_poly: Optional[Polygon] = None

    def __post_init__(self):
        if len(self.polygon) >= 3:
            self._shapely_poly = Polygon(self.polygon)

    def contains(self, x: float, y: float) -> bool:
        if self._shapely_poly is None:
            return False
        return self._shapely_poly.contains(Point(x, y)) or self._shapely_poly.boundary.distance(Point(x, y)) < 1.0


class ZoneClassifier:
    """
    Assigns zone to a person detection based on foot position.

    Args:
        layout_path: Path to store_layout.json.
        store_id: Store to filter zones for.
    """

    def __init__(self, zones: list[ZoneDefinition]) -> None:
        # Sort by priority descending (higher priority checked first)
        self._zones = sorted(zones, key=lambda z: z.priority, reverse=True)
        logger.info("ZoneClassifier loaded", extra={"zone_count": len(self._zones)})

    @classmethod
    def from_layout_file(cls, layout_path: str, store_id: str) -> "ZoneClassifier":
        """Load zones from store_layout.json."""
        with open(layout_path, "r") as f:
            layout = json.load(f)

        zones: list[ZoneDefinition] = []
        for store in layout.get("stores", []):
            if store.get("store_id") != store_id:
                continue
            for z in store.get("zones", []):
                zones.append(ZoneDefinition(
                    zone_id=z["zone_id"],
                    name=z["name"],
                    zone_type=z["zone_type"],
                    polygon=z["polygon"],
                    priority=z.get("priority", 0),
                ))

        return cls(zones)

    def classify(self, x: float, y: float) -> Optional[ZoneDefinition]:
        """
        Return the zone that contains (x, y), or None if no zone matches.
        Uses foot position (bottom-centre of bbox) for accuracy.
        """
        for zone in self._zones:
            if zone.contains(x, y):
                return zone
        return None

    def classify_bbox(self, bbox: dict) -> Optional[ZoneDefinition]:
        """Convenience: classify using bottom-centre of bounding box."""
        cx = (bbox["x1"] + bbox["x2"]) / 2.0
        cy = bbox["y2"]  # foot position
        return self.classify(cx, cy)

    def get_billing_zones(self) -> list[ZoneDefinition]:
        return [z for z in self._zones if z.zone_type == "BILLING"]

    def get_entry_zones(self) -> list[ZoneDefinition]:
        return [z for z in self._zones if z.zone_type == "ENTRY"]

    def get_exit_zones(self) -> list[ZoneDefinition]:
        return [z for z in self._zones if z.zone_type == "EXIT"]

    def get_all_zones(self) -> list[ZoneDefinition]:
        return self._zones
