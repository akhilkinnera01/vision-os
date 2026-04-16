"""Stateful event emission over scene and actor transitions."""

from __future__ import annotations

from common.models import ActorFrameState, Decision, SceneFeatures, TemporalState, VisionEvent
from common.policy import EventPolicy
from events.reducer import EventReducer


class EventEmitter:
    """Emit meaningful transitions instead of only exposing the current label."""

    def __init__(self, policy: EventPolicy) -> None:
        self.policy = policy
        self.reducer = EventReducer(policy)
        self._focus_sustained_active = False
        self._group_active = False
        self._collaboration_increasing_active = False
        self._unstable_active = False
        self._distraction_active_ids: set[int] = set()

    def update(
        self,
        timestamp: float,
        decision: Decision,
        temporal_state: TemporalState,
        actor_frame_state: ActorFrameState,
        features: SceneFeatures,
    ) -> list[VisionEvent]:
        events: list[VisionEvent] = []

        focus_sustained_now = (
            decision.label.value == "Focused Work"
            and temporal_state.metrics.focus_duration_seconds >= self.policy.focus_sustained_seconds
        )
        if focus_sustained_now and not self._focus_sustained_active:
            events.append(self.reducer.focus_sustained(timestamp, temporal_state))
        self._focus_sustained_active = focus_sustained_now

        active_distraction_ids = self.reducer.active_distraction_ids(actor_frame_state, temporal_state)
        for actor_id in sorted(active_distraction_ids - self._distraction_active_ids):
            events.append(self.reducer.distraction_started(timestamp, actor_id))
        for actor_id in sorted(self._distraction_active_ids - active_distraction_ids):
            events.append(self.reducer.distraction_resolved(timestamp, actor_id))
            actor = actor_frame_state.actors.get(actor_id)
            if actor and actor.interaction_state == "laptop_engaged":
                events.append(self.reducer.focus_resumed(timestamp, actor_id))
        self._distraction_active_ids = active_distraction_ids

        collaboration_events = self.reducer.collaboration_events(timestamp, features, temporal_state, self._group_active)
        collaboration_increasing_now = (
            features.multiple_people_clustered
            and features.person_count >= self.policy.group_person_count
            and (temporal_state.metrics.collaboration_increasing or not self._group_active)
        )
        if collaboration_increasing_now:
            if self._collaboration_increasing_active:
                collaboration_events = [
                    event for event in collaboration_events if event.event_type != "collaboration_increasing"
                ]
        self._collaboration_increasing_active = collaboration_increasing_now
        events.extend(collaboration_events)
        self._group_active = (
            features.multiple_people_clustered
            and features.person_count >= self.policy.group_person_count
        )

        events.extend(self.reducer.stability_events(timestamp, temporal_state, self._unstable_active))
        self._unstable_active = temporal_state.metrics.context_unstable
        return events
