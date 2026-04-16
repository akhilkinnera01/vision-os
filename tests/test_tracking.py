"""Tests for identity tracking and actor state."""

from __future__ import annotations

from common.models import BoundingBox, Detection
from common.policy import load_policy
from state.actor_store import ActorStore
from tracking.tracker import DetectionTracker


def make_detection(
    label: str,
    bbox: tuple[int, int, int, int],
    confidence: float = 0.95,
    track_id: int | None = None,
) -> Detection:
    box = BoundingBox(*bbox)
    return Detection(
        label=label,
        confidence=confidence,
        bbox=box,
        area_ratio=(box.area / float(1280 * 720)) if box.area else 0.0,
        track_id=track_id,
    )


def test_tracker_preserves_identity_across_nearby_frames() -> None:
    policy = load_policy("default")
    tracker = DetectionTracker(policy.tracking)

    first = tracker.update(
        timestamp=0.0,
        detections=[make_detection("person", (100, 100, 240, 420))],
        frame_shape=(720, 1280),
    )
    second = tracker.update(
        timestamp=0.4,
        detections=[make_detection("person", (112, 108, 252, 428))],
        frame_shape=(720, 1280),
    )

    assert first[0].track_id is not None
    assert second[0].track_id == first[0].track_id


def test_tracker_assigns_new_identity_after_expiry() -> None:
    policy = load_policy("default")
    tracker = DetectionTracker(policy.tracking)

    first = tracker.update(
        timestamp=0.0,
        detections=[make_detection("person", (100, 100, 240, 420))],
        frame_shape=(720, 1280),
    )
    tracker.update(
        timestamp=policy.tracking.max_idle_seconds + 0.5,
        detections=[],
        frame_shape=(720, 1280),
    )
    later = tracker.update(
        timestamp=policy.tracking.max_idle_seconds + 1.0,
        detections=[make_detection("person", (102, 102, 242, 422))],
        frame_shape=(720, 1280),
    )

    assert later[0].track_id != first[0].track_id


def test_actor_store_tracks_phone_then_laptop_return() -> None:
    policy = load_policy("default")
    actor_store = ActorStore(policy)

    actor_store.update(
        timestamp=0.0,
        detections=[
            make_detection("person", (240, 120, 420, 600), track_id=1),
            make_detection("laptop", (360, 360, 620, 560), track_id=2),
        ],
        frame_shape=(720, 1280),
    )
    actor_store.update(
        timestamp=1.0,
        detections=[
            make_detection("person", (250, 130, 430, 610), track_id=1),
            make_detection("cell phone", (380, 300, 440, 360), track_id=3),
        ],
        frame_shape=(720, 1280),
    )
    frame_state = actor_store.update(
        timestamp=2.0,
        detections=[
            make_detection("person", (258, 136, 438, 616), track_id=1),
            make_detection("laptop", (372, 364, 628, 564), track_id=2),
        ],
        frame_shape=(720, 1280),
    )

    actor = frame_state.actors[1]
    assert actor.dwell_seconds == 2.0
    assert actor.interaction_state == "laptop_engaged"
    assert actor.previous_interaction_state == "phone_engaged"
