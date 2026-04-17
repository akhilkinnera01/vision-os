"""Build zone-local feature sets from assignments."""

from __future__ import annotations

from collections import defaultdict

from common.models import ActorFrameState
from features.builder import FeatureBuilder
from zones.models import Zone, ZoneAssignment, ZoneFeatureSet


class ZoneFeatureBuilder:
    """Reuse the existing scene feature builder on assigned zone subsets."""

    def __init__(self, feature_builder: FeatureBuilder | None = None) -> None:
        self.feature_builder = feature_builder or FeatureBuilder()

    def build(
        self,
        zones: tuple[Zone, ...],
        assignments: tuple[ZoneAssignment, ...],
        frame_shape: tuple[int, int],
        actor_frame_state: ActorFrameState | None = None,
    ) -> tuple[ZoneFeatureSet, ...]:
        detections_by_zone: dict[str, list] = defaultdict(list)
        actor_ids_by_zone: dict[str, set[int]] = defaultdict(set)

        for assignment in assignments:
            detections_by_zone[assignment.zone_id].append(assignment.detection)
            if assignment.detection.track_id is not None and assignment.detection.label == "person":
                actor_ids_by_zone[assignment.zone_id].add(assignment.detection.track_id)

        zone_features: list[ZoneFeatureSet] = []
        for zone in zones:
            zone_actor_state = self._slice_actor_state(actor_frame_state, actor_ids_by_zone.get(zone.zone_id, set()))
            assigned_detections = detections_by_zone.get(zone.zone_id, [])
            features = self.feature_builder.build(assigned_detections, frame_shape, zone_actor_state)
            actor_track_ids = tuple(sorted(zone_actor_state.actors.keys()))
            occupied = features.person_count > 0 or features.active_track_count > 0 or features.occupied_ratio > 0.02
            zone_features.append(
                ZoneFeatureSet(
                    zone_id=zone.zone_id,
                    zone_name=zone.name,
                    zone_type=zone.zone_type,
                    features=features,
                    detection_count=len(assigned_detections),
                    occupied=occupied,
                    actor_track_ids=actor_track_ids,
                )
            )
        return tuple(zone_features)

    def _slice_actor_state(self, actor_frame_state: ActorFrameState | None, actor_ids: set[int]) -> ActorFrameState:
        if actor_frame_state is None or not actor_ids:
            return ActorFrameState()

        return ActorFrameState(
            actors={actor_id: actor for actor_id, actor in actor_frame_state.actors.items() if actor_id in actor_ids},
            entered_track_ids=[actor_id for actor_id in actor_frame_state.entered_track_ids if actor_id in actor_ids],
            departed_track_ids=[actor_id for actor_id in actor_frame_state.departed_track_ids if actor_id in actor_ids],
        )
