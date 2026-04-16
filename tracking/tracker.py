"""Assign stable identities to detections across frames."""

from __future__ import annotations

from common.models import Detection
from common.policy import TrackingPolicy
from tracking.matching import bbox_iou, normalized_center_distance
from tracking.track_store import TrackStore


class DetectionTracker:
    """Greedy IoU plus center-distance tracker for lightweight deterministic identity."""

    def __init__(self, policy: TrackingPolicy) -> None:
        self.policy = policy
        self.store = TrackStore(policy)

    def update(
        self,
        timestamp: float,
        detections: list[Detection],
        frame_shape: tuple[int, int],
    ) -> list[Detection]:
        self.store.prune(timestamp)
        if not detections:
            return []

        if detections and all(detection.track_id is not None for detection in detections):
            for detection in detections:
                self.store.upsert(
                    detection.track_id or 0,
                    detection.label,
                    detection.bbox,
                    detection.confidence,
                    timestamp,
                )
            return detections

        active_tracks = self.store.active_tracks(timestamp)
        assignments: dict[int, int] = {}
        used_tracks: set[int] = set()
        candidates: list[tuple[float, int, int]] = []

        for detection_index, detection in enumerate(detections):
            for track in active_tracks:
                if detection.label != track.label:
                    continue
                iou = bbox_iou(detection.bbox, track.bbox)
                center_distance = normalized_center_distance(detection.bbox, track.bbox, frame_shape)
                if iou < self.policy.min_iou and center_distance > self.policy.max_center_distance:
                    continue
                score = iou + max(0.0, 1.0 - center_distance / max(self.policy.max_center_distance, 1e-6)) * 0.5
                candidates.append((score, detection_index, track.track_id))

        for _, detection_index, track_id in sorted(candidates, reverse=True):
            if detection_index in assignments or track_id in used_tracks:
                continue
            assignments[detection_index] = track_id
            used_tracks.add(track_id)

        tracked: list[Detection] = []
        for index, detection in enumerate(detections):
            if index in assignments:
                track = self.store.upsert(
                    assignments[index],
                    detection.label,
                    detection.bbox,
                    detection.confidence,
                    timestamp,
                )
            else:
                track = self.store.create(
                    detection.label,
                    detection.bbox,
                    detection.confidence,
                    timestamp,
                )
            tracked.append(detection.with_track_id(track.track_id))
        return tracked
