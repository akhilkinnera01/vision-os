"""Convert raw detections into frame-local and spatial scene features."""

from __future__ import annotations

from collections import Counter
from itertools import combinations
from math import dist, sqrt

from common.models import Detection, SceneFeatures


class FeatureBuilder:
    """Build simple booleans, counts, and scores from the detection stream."""

    DESK_OBJECTS = {"laptop", "keyboard", "mouse", "book", "chair", "monitor", "tv"}
    ROOM_OBJECTS = {"couch", "bed", "tv", "remote", "cell phone"}

    def build(self, detections: list[Detection], frame_shape: tuple[int, int]) -> SceneFeatures:
        """Aggregate detections into a compact feature set for reasoning."""
        counts = Counter(detection.label for detection in detections)
        occupied_ratio = min(sum(detection.area_ratio for detection in detections), 1.0)
        dominant_label = counts.most_common(1)[0][0] if counts else "none"
        diagonal = sqrt(frame_shape[0] ** 2 + frame_shape[1] ** 2)
        center_x = frame_shape[1] / 2.0
        center_y = frame_shape[0] / 2.0

        workspace_score = (
            counts.get("laptop", 0) * 1.2
            + counts.get("keyboard", 0) * 0.9
            + counts.get("mouse", 0) * 0.7
            + counts.get("book", 0) * 0.4
            + counts.get("monitor", 0) * 0.9
            + counts.get("tv", 0) * 0.4
        )
        collaboration_score = counts.get("person", 0) * 1.0 + counts.get("chair", 0) * 0.2
        casual_score = (
            counts.get("cell phone", 0) * 1.0
            + counts.get("remote", 0) * 0.8
            + counts.get("couch", 0) * 1.0
            + counts.get("bed", 0) * 1.0
            + counts.get("tv", 0) * 0.35
        )

        person_laptop_distance = self._nearest_normalized_distance(detections, "person", "laptop", diagonal)
        person_phone_distance = self._nearest_normalized_distance(
            detections,
            "person",
            "cell phone",
            diagonal,
        )
        people_cluster_score = self._people_cluster_score(detections, diagonal)

        monitor_candidates = [detection for detection in detections if detection.label in {"monitor", "tv"}]
        center_dominance_score = 0.0
        centered_monitor = False
        for detection in monitor_candidates:
            x, y = detection.bbox.center
            x_score = max(0.0, 1.0 - abs(x - center_x) / max(center_x, 1.0))
            y_score = max(0.0, 1.0 - abs(y - center_y) / max(center_y, 1.0))
            candidate_score = detection.area_ratio * 4.0 + (x_score + y_score) / 2.0
            if candidate_score > center_dominance_score:
                center_dominance_score = candidate_score
                centered_monitor = detection.area_ratio > 0.05 and x_score > 0.65 and y_score > 0.65

        desk_like_score = self._desk_like_score(detections)
        room_like_score = self._room_like_score(detections)

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
            occupied_ratio=occupied_ratio,
            dominant_label=dominant_label,
            laptop_near_person=person_laptop_distance < 0.22,
            phone_near_person=person_phone_distance < 0.18,
            multiple_people_clustered=people_cluster_score > 0.55,
            centered_monitor=centered_monitor,
            desk_like_score=desk_like_score,
            room_like_score=room_like_score,
            person_laptop_distance=round(person_laptop_distance, 3),
            person_phone_distance=round(person_phone_distance, 3),
            people_cluster_score=round(people_cluster_score, 3),
            center_dominance_score=round(center_dominance_score, 3),
        )

    def _nearest_normalized_distance(
        self,
        detections: list[Detection],
        left_label: str,
        right_label: str,
        diagonal: float,
    ) -> float:
        left = [detection for detection in detections if detection.label == left_label]
        right = [detection for detection in detections if detection.label == right_label]
        if not left or not right:
            return 1.0
        return min(dist(a.bbox.center, b.bbox.center) / max(diagonal, 1.0) for a in left for b in right)

    def _people_cluster_score(self, detections: list[Detection], diagonal: float) -> float:
        people = [detection for detection in detections if detection.label == "person"]
        if len(people) < 2:
            return 0.0
        average_distance = sum(
            dist(left.bbox.center, right.bbox.center) for left, right in combinations(people, 2)
        ) / len(list(combinations(people, 2)))
        normalized_distance = average_distance / max(diagonal, 1.0)
        return max(0.0, 1.0 - normalized_distance / 0.35)

    def _desk_like_score(self, detections: list[Detection]) -> float:
        if not detections:
            return 0.0
        bottom_half_objects = 0
        desk_objects = 0
        for detection in detections:
            if detection.label in self.DESK_OBJECTS:
                desk_objects += 1
                if detection.bbox.center[1] >= 240:
                    bottom_half_objects += 1
        return min(1.0, desk_objects * 0.2 + bottom_half_objects * 0.12)

    def _room_like_score(self, detections: list[Detection]) -> float:
        room_objects = sum(1 for detection in detections if detection.label in self.ROOM_OBJECTS)
        return min(1.0, room_objects * 0.25)
