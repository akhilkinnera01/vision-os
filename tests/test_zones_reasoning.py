"""Tests for zone-local context, decisions, and temporal memory."""

from __future__ import annotations

from common.models import SceneFeatures
from zones import (
    ZoneContextLabel,
    ZoneDecisionEngine,
    ZoneFeatureSet,
    ZoneRulesEngine,
    ZoneTemporalMemory,
    ZoneTemporalState,
    ZoneType,
)


def _feature_set(zone_id: str, **feature_values) -> ZoneFeatureSet:
    return ZoneFeatureSet(
        zone_id=zone_id,
        zone_name=zone_id.title(),
        zone_type=ZoneType.OCCUPANCY,
        features=SceneFeatures(**feature_values),
        detection_count=feature_values.get("counts", {}).get("person", 0),
        occupied=feature_values.get("person_count", 0) > 0 or feature_values.get("occupied_ratio", 0.0) > 0.02,
    )


def test_zone_rules_distinguish_empty_focus_and_group_activity() -> None:
    rules = ZoneRulesEngine()

    empty = rules.infer(_feature_set("desk_a"))
    focused = rules.infer(
        _feature_set(
            "desk_b",
            person_count=1,
            workspace_score=1.3,
            laptop_near_person=True,
            occupied_ratio=0.18,
            counts={"person": 1, "laptop": 1},
        )
    )
    group = rules.infer(
        _feature_set(
            "whiteboard",
            person_count=2,
            collaboration_score=2.2,
            multiple_people_clustered=True,
            occupied_ratio=0.25,
            counts={"person": 2},
        )
    )

    assert empty.label == ZoneContextLabel.EMPTY
    assert focused.label == ZoneContextLabel.SOLO_FOCUS
    assert group.label == ZoneContextLabel.GROUP_ACTIVITY


def test_zone_decision_holds_when_temporal_state_is_unstable() -> None:
    decision_engine = ZoneDecisionEngine()
    context = ZoneRulesEngine().infer(
        _feature_set("desk_a", person_count=1, workspace_score=0.9, occupied_ratio=0.12, counts={"person": 1})
    )
    unstable_state = ZoneTemporalState(stability_score=0.32)

    decision = decision_engine.decide(context, unstable_state)

    assert decision.action == "Hold zone label until state stabilizes"
    assert decision.confidence < context.confidence


def test_zone_temporal_memory_tracks_focus_and_occupancy_duration() -> None:
    memory = ZoneTemporalMemory(window_seconds=10.0)
    rules = ZoneRulesEngine()
    feature_set = _feature_set(
        "desk_a",
        person_count=1,
        workspace_score=1.4,
        laptop_near_person=True,
        occupied_ratio=0.2,
        counts={"person": 1, "laptop": 1},
    )

    states = memory.update(0.0, (feature_set,), {"desk_a": rules.infer(feature_set)})
    assert states["desk_a"].current_label_duration_seconds == 0.0

    states = memory.update(4.0, (feature_set,), {"desk_a": rules.infer(feature_set)})
    states = memory.update(8.0, (feature_set,), {"desk_a": rules.infer(feature_set)})
    state = states["desk_a"]

    assert state.dominant_label == ZoneContextLabel.SOLO_FOCUS
    assert state.current_label_duration_seconds == 8.0
    assert state.occupied_duration_seconds == 8.0
    assert "solo_focus for 8.0s" in state.notes
