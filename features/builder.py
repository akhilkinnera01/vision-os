"""Convert raw detections into lightweight scene features."""

from __future__ import annotations

from collections import Counter

from common.models import Detection, SceneFeatures


class FeatureBuilder:
    """Build simple booleans, counts, and scores from the detection stream."""

    WORK_OBJECTS = {"laptop", "keyboard", "mouse", "book", "tv", "monitor"}
    CASUAL_OBJECTS = {"cell phone", "remote", "couch", "bed", "tv"}

    def build(self, detections: list[Detection], frame_shape: tuple[int, int]) -> SceneFeatures:
        """Aggregate detections into a compact feature set for reasoning."""
        counts = Counter(detection.label for detection in detections)
        occupied_ratio = sum(detection.area_ratio for detection in detections)
        dominant_label = counts.most_common(1)[0][0] if counts else "none"

        workspace_score = (
            counts.get("laptop", 0) * 1.2
            + counts.get("keyboard", 0) * 0.9
            + counts.get("mouse", 0) * 0.6
            + counts.get("book", 0) * 0.5
            + counts.get("tv", 0) * 0.4
            + counts.get("monitor", 0) * 0.8
        )
        collaboration_score = counts.get("person", 0) * 1.0 + counts.get("chair", 0) * 0.2
        casual_score = (
            counts.get("cell phone", 0) * 1.0
            + counts.get("remote", 0) * 0.8
            + counts.get("couch", 0) * 1.0
            + counts.get("bed", 0) * 1.0
            + counts.get("tv", 0) * 0.5
        )

        return SceneFeatures(
            counts=dict(counts),
            person_count=counts.get("person", 0),
            has_laptop=counts.get("laptop", 0) > 0,
            has_phone=counts.get("cell phone", 0) > 0,
            has_book=counts.get("book", 0) > 0,
            has_keyboard=counts.get("keyboard", 0) > 0,
            has_mouse=counts.get("mouse", 0) > 0,
            has_monitor=counts.get("tv", 0) > 0 or counts.get("monitor", 0) > 0,
            has_chair=counts.get("chair", 0) > 0,
            workspace_score=workspace_score,
            collaboration_score=collaboration_score,
            casual_score=casual_score,
            occupied_ratio=min(occupied_ratio, 1.0),
            dominant_label=dominant_label,
        )

