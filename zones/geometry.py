"""Geometry helpers for zone hit testing."""

from __future__ import annotations

from common.models import BoundingBox
from zones.models import Zone, ZonePoint


def point_in_polygon(point: tuple[float, float], polygon: tuple[ZonePoint, ...], *, boundary_inclusive: bool = True) -> bool:
    """Return whether a point lies inside a polygon using ray casting."""
    x, y = point
    inside = False

    for index, current in enumerate(polygon):
        nxt = polygon[(index + 1) % len(polygon)]
        if boundary_inclusive and _point_on_segment(point, current, nxt):
            return True

        intersects = (current.y > y) != (nxt.y > y)
        if not intersects:
            continue

        cross_x = ((nxt.x - current.x) * (y - current.y) / (nxt.y - current.y)) + current.x
        if cross_x == x and boundary_inclusive:
            return True
        if cross_x > x:
            inside = not inside

    return inside


def sample_points_for_bbox(bbox: BoundingBox) -> tuple[tuple[float, float], ...]:
    """Return stable sample points used for coarse polygon coverage scoring."""
    center_x, center_y = bbox.center
    return (
        (center_x, center_y),
        (bbox.x1, bbox.y1),
        (bbox.x2, bbox.y1),
        (bbox.x2, bbox.y2),
        (bbox.x1, bbox.y2),
    )


def coverage_ratio(bbox: BoundingBox, zone: Zone) -> float:
    """Approximate how much of a detection falls within a zone."""
    samples = sample_points_for_bbox(bbox)
    hits = sum(1 for point in samples if point_in_polygon(point, zone.polygon))
    return hits / len(samples)


def _point_on_segment(point: tuple[float, float], left: ZonePoint, right: ZonePoint) -> bool:
    px, py = point
    cross = (py - left.y) * (right.x - left.x) - (px - left.x) * (right.y - left.y)
    if abs(cross) > 1e-9:
        return False

    dot = (px - left.x) * (right.x - left.x) + (py - left.y) * (right.y - left.y)
    if dot < 0:
        return False

    squared_length = (right.x - left.x) ** 2 + (right.y - left.y) ** 2
    return dot <= squared_length
