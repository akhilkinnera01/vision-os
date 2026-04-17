"""Tests for zone-local feature extraction."""

from __future__ import annotations

from common.models import ActorFrameState, ActorState, BoundingBox, Detection
from zones import Zone, ZoneAssigner, ZoneFeatureBuilder, ZonePoint, ZoneType


def _zone(zone_id: str, polygon: tuple[tuple[float, float], ...], zone_type: ZoneType = ZoneType.OCCUPANCY) -> Zone:
    return Zone(
        zone_id=zone_id,
        name=zone_id.replace("_", " ").title(),
        zone_type=zone_type,
        polygon=tuple(ZonePoint(x, y) for x, y in polygon),
    )


def _detection(label: str, bbox: BoundingBox, *, track_id: int | None = None, area_ratio: float = 0.05) -> Detection:
    return Detection(label=label, confidence=0.92, bbox=bbox, area_ratio=area_ratio, track_id=track_id)


def test_zone_feature_builder_generates_empty_and_active_zone_sets() -> None:
    zones = (
        _zone("desk_a", ((0, 0), (400, 0), (400, 400), (0, 400))),
        _zone("desk_b", ((500, 0), (900, 0), (900, 400), (500, 400))),
    )
    detections = [
        _detection("person", BoundingBox(80, 80, 180, 320), track_id=7),
        _detection("laptop", BoundingBox(120, 240, 250, 330)),
    ]
    assignments = ZoneAssigner().assign(detections, zones)
    actor_frame_state = ActorFrameState(
        actors={
            7: ActorState(
                track_id=7,
                label="person",
                first_seen_timestamp=0.0,
                last_seen_timestamp=4.0,
                dwell_seconds=4.0,
                interaction_state="laptop_engaged",
            )
        }
    )

    zone_sets = ZoneFeatureBuilder().build(zones, assignments, (720, 1280), actor_frame_state)

    assert len(zone_sets) == 2
    by_id = {zone_set.zone_id: zone_set for zone_set in zone_sets}
    assert by_id["desk_a"].occupied is True
    assert by_id["desk_a"].features.person_count == 1
    assert by_id["desk_a"].features.laptop_near_person is True
    assert by_id["desk_a"].actor_track_ids == (7,)
    assert by_id["desk_b"].occupied is False
    assert by_id["desk_b"].features.person_count == 0
    assert by_id["desk_b"].detection_count == 0


def test_zone_feature_builder_uses_zone_local_actor_state_for_group_metrics() -> None:
    zones = (
        _zone("focus_desk", ((0, 0), (400, 0), (400, 500), (0, 500))),
        _zone("whiteboard", ((450, 0), (900, 0), (900, 500), (450, 500)), zone_type=ZoneType.ACTIVITY),
    )
    detections = [
        _detection("person", BoundingBox(500, 50, 580, 260), track_id=11),
        _detection("person", BoundingBox(590, 80, 680, 290), track_id=12),
        _detection("chair", BoundingBox(520, 260, 600, 430)),
    ]
    assignments = ZoneAssigner().assign(detections, zones)
    actor_frame_state = ActorFrameState(
        actors={
            11: ActorState(11, "person", 0.0, 6.0, 6.0, interaction_state="idle"),
            12: ActorState(12, "person", 0.0, 5.5, 5.5, interaction_state="phone_engaged"),
        }
    )

    zone_sets = ZoneFeatureBuilder().build(zones, assignments, (720, 1280), actor_frame_state)
    by_id = {zone_set.zone_id: zone_set for zone_set in zone_sets}

    assert by_id["whiteboard"].occupied is True
    assert by_id["whiteboard"].features.person_count == 2
    assert by_id["whiteboard"].features.multiple_people_clustered is True
    assert by_id["whiteboard"].features.distracted_person_count == 1
    assert by_id["whiteboard"].actor_track_ids == (11, 12)
    assert by_id["focus_desk"].features.person_count == 0
