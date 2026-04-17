"""Assign detections to their primary configured zone."""

from __future__ import annotations

from common.models import Detection
from zones.geometry import coverage_ratio, point_in_polygon
from zones.models import Zone, ZoneAssignment


class ZoneAssigner:
    """Resolve one primary zone per detection using stable heuristics."""

    LARGE_OBJECT_LABELS = {"laptop", "monitor", "tv", "couch", "bed"}

    def __init__(self, *, min_coverage_ratio: float = 0.4) -> None:
        self.min_coverage_ratio = min_coverage_ratio

    def assign(self, detections: list[Detection], zones: tuple[Zone, ...]) -> tuple[ZoneAssignment, ...]:
        """Assign detections to the highest-confidence enabled zone."""
        assignments: list[ZoneAssignment] = []
        for detection in detections:
            best_zone: Zone | None = None
            best_score = 0.0
            best_method = "center"
            for zone in zones:
                if not zone.enabled:
                    continue
                method, score = self._score_detection(detection, zone)
                if score > best_score:
                    best_zone = zone
                    best_score = score
                    best_method = method
            if best_zone is None or best_score <= 0.0:
                continue
            assignments.append(
                ZoneAssignment(
                    zone_id=best_zone.zone_id,
                    detection=detection,
                    method=best_method,
                    score=round(best_score, 3),
                )
            )
        return tuple(assignments)

    def _score_detection(self, detection: Detection, zone: Zone) -> tuple[str, float]:
        if detection.label in self.LARGE_OBJECT_LABELS:
            score = coverage_ratio(detection.bbox, zone)
            if score >= self.min_coverage_ratio:
                return ("coverage", score)
            return ("coverage", 0.0)

        inside = point_in_polygon(detection.bbox.center, zone.polygon)
        return ("center", 1.0 if inside else 0.0)
