"""Unit tests for Zone Classifier."""
import pytest
from pipeline.zone_classifier import ZoneClassifier, ZoneDefinition


def make_classifier():
    zones = [
        ZoneDefinition(
            zone_id="ZONE_ENTRY_01",
            name="Entry",
            zone_type="ENTRY",
            polygon=[[0, 580], [200, 580], [200, 720], [0, 720]],
            priority=10,
        ),
        ZoneDefinition(
            zone_id="ZONE_BILLING_01",
            name="Billing",
            zone_type="BILLING",
            polygon=[[800, 300], [1080, 300], [1080, 720], [800, 720]],
            priority=8,
        ),
        ZoneDefinition(
            zone_id="ZONE_SKINCARE_01",
            name="Skincare",
            zone_type="DISPLAY",
            polygon=[[200, 300], [500, 300], [500, 580], [200, 580]],
            priority=5,
        ),
    ]
    return ZoneClassifier(zones)


class TestZoneClassifier:

    def test_point_in_entry_zone(self):
        clf = make_classifier()
        zone = clf.classify(100, 650)
        assert zone is not None
        assert zone.zone_id == "ZONE_ENTRY_01"

    def test_point_in_billing_zone(self):
        clf = make_classifier()
        zone = clf.classify(900, 500)
        assert zone is not None
        assert zone.zone_id == "ZONE_BILLING_01"

    def test_point_in_display_zone(self):
        clf = make_classifier()
        zone = clf.classify(350, 450)
        assert zone is not None
        assert zone.zone_id == "ZONE_SKINCARE_01"

    def test_point_not_in_any_zone(self):
        clf = make_classifier()
        # Open floor area not covered by any zone
        zone = clf.classify(650, 150)
        assert zone is None

    def test_classify_bbox_uses_foot_position(self):
        """Bottom-centre of bbox should be used, not head."""
        clf = make_classifier()
        # Bbox with head above entry zone, feet in entry zone
        bbox = {"x1": 50, "y1": 400, "x2": 150, "y2": 650}
        # Foot position: cx=100, cy=650 → inside entry zone
        zone = clf.classify_bbox(bbox)
        assert zone is not None
        assert zone.zone_id == "ZONE_ENTRY_01"

    def test_priority_ordering(self):
        """Higher priority zone wins when overlapping."""
        # Create two overlapping zones
        zones = [
            ZoneDefinition(
                zone_id="ZONE_HIGH",
                name="High Priority",
                zone_type="ENTRY",
                polygon=[[0, 0], [200, 0], [200, 200], [0, 200]],
                priority=10,
            ),
            ZoneDefinition(
                zone_id="ZONE_LOW",
                name="Low Priority",
                zone_type="DISPLAY",
                polygon=[[0, 0], [200, 0], [200, 200], [0, 200]],
                priority=5,
            ),
        ]
        clf = ZoneClassifier(zones)
        zone = clf.classify(100, 100)
        assert zone.zone_id == "ZONE_HIGH"

    def test_get_billing_zones(self):
        clf = make_classifier()
        billing = clf.get_billing_zones()
        assert len(billing) == 1
        assert billing[0].zone_type == "BILLING"

    def test_get_entry_zones(self):
        clf = make_classifier()
        entries = clf.get_entry_zones()
        assert len(entries) == 1
        assert entries[0].zone_type == "ENTRY"

    def test_empty_polygon_no_crash(self):
        zones = [
            ZoneDefinition(
                zone_id="BAD_ZONE",
                name="Bad",
                zone_type="DISPLAY",
                polygon=[[0, 0]],  # only 1 point
                priority=5,
            )
        ]
        clf = ZoneClassifier(zones)
        zone = clf.classify(0, 0)
        assert zone is None

    def test_boundary_point_classified(self):
        """Points on boundary should be classified inside."""
        clf = make_classifier()
        # Point on boundary of skincare zone
        zone = clf.classify(200, 440)  # on left edge
        assert zone is not None
