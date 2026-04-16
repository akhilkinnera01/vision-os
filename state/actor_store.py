"""Per-track actor memory for interaction and dwell state."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import dist

from common.models import ActorFrameState, ActorState, Detection
from common.policy import VisionPolicy


@dataclass(slots=True)
class _ActorRecord:
    track_id: int
    label: str
    first_seen_timestamp: float
    last_seen_timestamp: float
    interaction_state: str = "idle"


class ActorStore:
    """Track per-person dwell and interaction transitions across frames."""

    def __init__(self, policy: VisionPolicy) -> None:
        self.policy = policy
        self._records: dict[int, _ActorRecord] = {}

    def update(
        self,
        timestamp: float,
        detections: list[Detection],
        frame_shape: tuple[int, int],
    ) -> ActorFrameState:
        visible_people = [
            detection for detection in detections if detection.label == "person" and detection.track_id is not None
        ]
        visible_ids = {detection.track_id or 0 for detection in visible_people}
        diagonal = max((frame_shape[0] ** 2 + frame_shape[1] ** 2) ** 0.5, 1.0)

        entered_track_ids: list[int] = []
        actors: dict[int, ActorState] = {}
        person_distances = self._person_neighbors(visible_people, diagonal)

        for detection in visible_people:
            track_id = detection.track_id or 0
            record = self._records.get(track_id)
            if record is None:
                record = _ActorRecord(
                    track_id=track_id,
                    label=detection.label,
                    first_seen_timestamp=timestamp,
                    last_seen_timestamp=timestamp,
                )
                self._records[track_id] = record
                entered_track_ids.append(track_id)

            previous_interaction_state = record.interaction_state
            interaction_state = self._interaction_state(detection, detections, diagonal)
            record.last_seen_timestamp = timestamp
            record.interaction_state = interaction_state

            focus_score = 0.85 if interaction_state == "laptop_engaged" else 0.2
            distraction_score = 0.85 if interaction_state == "phone_engaged" else 0.1

            actors[track_id] = ActorState(
                track_id=track_id,
                label=detection.label,
                first_seen_timestamp=record.first_seen_timestamp,
                last_seen_timestamp=record.last_seen_timestamp,
                dwell_seconds=round(timestamp - record.first_seen_timestamp, 2),
                interaction_state=interaction_state,
                previous_interaction_state=previous_interaction_state,
                nearby_track_ids=person_distances.get(track_id, []),
                focus_score=focus_score,
                distraction_score=distraction_score,
            )

        departed_track_ids: list[int] = []
        for track_id, record in list(self._records.items()):
            if track_id in visible_ids:
                continue
            if timestamp - record.last_seen_timestamp > self.policy.tracking.max_idle_seconds:
                departed_track_ids.append(track_id)
                self._records.pop(track_id, None)

        return ActorFrameState(
            actors=actors,
            entered_track_ids=sorted(entered_track_ids),
            departed_track_ids=sorted(departed_track_ids),
        )

    def _interaction_state(
        self,
        person: Detection,
        detections: list[Detection],
        diagonal: float,
    ) -> str:
        laptop_distance = self._nearest_distance(person, detections, "laptop", diagonal)
        phone_distance = self._nearest_distance(person, detections, "cell phone", diagonal)
        if laptop_distance <= self.policy.features.laptop_near_person_distance:
            return "laptop_engaged"
        if phone_distance <= self.policy.features.phone_near_person_distance:
            return "phone_engaged"
        return "idle"

    def _nearest_distance(
        self,
        person: Detection,
        detections: list[Detection],
        label: str,
        diagonal: float,
    ) -> float:
        candidates = [detection for detection in detections if detection.label == label]
        if not candidates:
            return 1.0
        return min(dist(person.bbox.center, candidate.bbox.center) / diagonal for candidate in candidates)

    def _person_neighbors(
        self,
        people: list[Detection],
        diagonal: float,
    ) -> dict[int, list[int]]:
        neighbors: dict[int, list[int]] = {detection.track_id or 0: [] for detection in people}
        for left, right in combinations(people, 2):
            distance = dist(left.bbox.center, right.bbox.center) / diagonal
            if distance <= self.policy.features.people_cluster_reference_distance:
                neighbors[left.track_id or 0].append(right.track_id or 0)
                neighbors[right.track_id or 0].append(left.track_id or 0)
        return neighbors
