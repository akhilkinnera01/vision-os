"""Tests for polygon hit testing and zone assignment."""

from __future__ import annotations

from common.models import BoundingBox, Detection
from zones import Zone, ZoneAssigner, ZonePoint, ZoneType
from zones.geometry import coverage_ratio, point_in_polygon


def _zone(
    zone_id: str,
    *,
    polygon: tuple[tuple[float, float], ...],
    zone_type: ZoneType = ZoneType.OCCUPANCY,
    enabled: bool = True,
) -> Zone:
    return Zone(
        zone_id=zone_id,
        name=zone_id.replace("_", " ").title(),
        zone_type=zone_type,
        polygon=tuple(ZonePoint(x, y) for x, y in polygon),
        enabled=enabled,
    )


def _detection(label: str, bbox: BoundingBox, *, track_id: int | None = None) -> Detection:
    return Detection(label=label, confidence=0.9, bbox=bbox, area_ratio=0.05, track_id=track_id)


def test_point_in_polygon_is_boundary_inclusive() -> None:
    polygon = (
        ZonePoint(0.0, 0.0),
        ZonePoint(10.0, 0.0),
        ZonePoint(10.0, 10.0),
        ZonePoint(0.0, 10.0),
    )

    assert point_in_polygon((5.0, 5.0), polygon) is True
    assert point_in_polygon((10.0, 5.0), polygon) is True
    assert point_in_polygon((11.0, 5.0), polygon) is False


def test_coverage_ratio_scores_large_objects_by_sample_points() -> None:
    zone = _zone("desk_a", polygon=((0, 0), (100, 0), (100, 100), (0, 100)))
    detection = _detection("laptop", BoundingBox(20, 20, 80, 80))

    assert coverage_ratio(detection.bbox, zone) == 1.0


def test_assigner_prefers_first_matching_zone_when_overlapping_scores_tie() -> None:
    assigner = ZoneAssigner()
    overlapping = (
        _zone("desk_a", polygon=((0, 0), (120, 0), (120, 120), (0, 120))),
        _zone("desk_b", polygon=((40, 40), (160, 40), (160, 160), (40, 160))),
    )
    person = _detection("person", BoundingBox(60, 60, 90, 120), track_id=1)

    assignments = assigner.assign([person], overlapping)

    assert len(assignments) == 1
    assert assignments[0].zone_id == "desk_a"
    assert assignments[0].method == "center"


def test_assigner_skips_disabled_zones_and_requires_large_object_coverage() -> None:
    assigner = ZoneAssigner(min_coverage_ratio=0.61)
    zones = (
        _zone("desk_a", polygon=((0, 0), (100, 0), (100, 100), (0, 100)), enabled=False),
        _zone("desk_b", polygon=((120, 0), (220, 0), (220, 100), (120, 100))),
    )
    laptop = _detection("laptop", BoundingBox(90, 10, 170, 90))

    assignments = assigner.assign([laptop], zones)

    assert len(assignments) == 0
