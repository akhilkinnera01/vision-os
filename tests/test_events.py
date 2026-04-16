"""Tests for typed event emission."""

from __future__ import annotations

from common.models import (
    ActorFrameState,
    ActorState,
    ContextLabel,
    Decision,
    SceneFeatures,
    SceneMetrics,
    TemporalState,
)
from common.policy import load_policy
from events.emitter import EventEmitter


def make_actor_state(track_id: int, interaction_state: str, previous: str = "idle") -> ActorState:
    return ActorState(
        track_id=track_id,
        label="person",
        first_seen_timestamp=0.0,
        last_seen_timestamp=1.0,
        dwell_seconds=1.0,
        interaction_state=interaction_state,
        previous_interaction_state=previous,
        nearby_track_ids=[],
        focus_score=0.8 if interaction_state == "laptop_engaged" else 0.2,
        distraction_score=0.8 if interaction_state == "phone_engaged" else 0.1,
    )


def make_decision(label: ContextLabel) -> Decision:
    return Decision(
        label=label,
        confidence=0.8,
        action="observe",
        scene_metrics=SceneMetrics(),
    )


def test_focus_sustained_emits_once() -> None:
    policy = load_policy("default")
    emitter = EventEmitter(policy.events)
    actor_state = ActorFrameState(actors={1: make_actor_state(1, "laptop_engaged")})

    first = emitter.update(
        timestamp=0.0,
        decision=make_decision(ContextLabel.FOCUSED_WORK),
        temporal_state=TemporalState(metrics=SceneMetrics(focus_duration_seconds=2.0, stability_score=0.7)),
        actor_frame_state=actor_state,
        features=SceneFeatures(),
    )
    second = emitter.update(
        timestamp=6.5,
        decision=make_decision(ContextLabel.FOCUSED_WORK),
        temporal_state=TemporalState(metrics=SceneMetrics(focus_duration_seconds=6.5, stability_score=0.78)),
        actor_frame_state=actor_state,
        features=SceneFeatures(),
    )

    assert first == []
    assert [event.event_type for event in second] == ["focus_sustained"]


def test_distraction_lifecycle_emits_start_and_resolution() -> None:
    policy = load_policy("default")
    emitter = EventEmitter(policy.events)

    emitter.update(
        timestamp=0.0,
        decision=make_decision(ContextLabel.FOCUSED_WORK),
        temporal_state=TemporalState(metrics=SceneMetrics(distraction_score=0.1, stability_score=0.8)),
        actor_frame_state=ActorFrameState(actors={1: make_actor_state(1, "laptop_engaged")}),
        features=SceneFeatures(),
    )
    started = emitter.update(
        timestamp=1.0,
        decision=make_decision(ContextLabel.FOCUSED_WORK),
        temporal_state=TemporalState(
            metrics=SceneMetrics(distraction_score=0.75, distraction_spike=True, stability_score=0.58)
        ),
        actor_frame_state=ActorFrameState(actors={1: make_actor_state(1, "phone_engaged", previous="laptop_engaged")}),
        features=SceneFeatures(phone_near_person=True),
    )
    resolved = emitter.update(
        timestamp=2.0,
        decision=make_decision(ContextLabel.FOCUSED_WORK),
        temporal_state=TemporalState(metrics=SceneMetrics(distraction_score=0.18, stability_score=0.76)),
        actor_frame_state=ActorFrameState(actors={1: make_actor_state(1, "laptop_engaged", previous="phone_engaged")}),
        features=SceneFeatures(laptop_near_person=True),
    )

    assert [event.event_type for event in started] == ["distraction_started"]
    assert [event.event_type for event in resolved] == ["distraction_resolved", "focus_resumed"]


def test_collaboration_events_emit_form_and_disperse() -> None:
    policy = load_policy("default")
    emitter = EventEmitter(policy.events)

    emitter.update(
        timestamp=0.0,
        decision=make_decision(ContextLabel.FOCUSED_WORK),
        temporal_state=TemporalState(metrics=SceneMetrics(collaboration_score=0.12, stability_score=0.8)),
        actor_frame_state=ActorFrameState(actors={1: make_actor_state(1, "laptop_engaged")}),
        features=SceneFeatures(person_count=1, multiple_people_clustered=False),
    )
    formed = emitter.update(
        timestamp=1.0,
        decision=make_decision(ContextLabel.GROUP_ACTIVITY),
        temporal_state=TemporalState(
            metrics=SceneMetrics(collaboration_score=0.72, collaboration_increasing=True, stability_score=0.7)
        ),
        actor_frame_state=ActorFrameState(
            actors={
                1: make_actor_state(1, "idle"),
                2: make_actor_state(2, "idle"),
            }
        ),
        features=SceneFeatures(person_count=2, multiple_people_clustered=True),
    )
    dispersed = emitter.update(
        timestamp=2.0,
        decision=make_decision(ContextLabel.FOCUSED_WORK),
        temporal_state=TemporalState(metrics=SceneMetrics(collaboration_score=0.18, stability_score=0.74)),
        actor_frame_state=ActorFrameState(actors={1: make_actor_state(1, "laptop_engaged")}),
        features=SceneFeatures(person_count=1, multiple_people_clustered=False),
    )

    assert [event.event_type for event in formed] == ["group_formed", "collaboration_increasing"]
    assert [event.event_type for event in dispersed] == ["group_dispersed"]
