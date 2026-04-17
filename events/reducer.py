"""Reducer helpers for event lifecycle transitions."""

from __future__ import annotations

from common.models import ActorFrameState, SceneFeatures, TemporalState
from common.policy import EventPolicy
from events.models import CollaborationEvent, DistractionEvent, SceneTransitionEvent, StabilityEvent, ZoneEvent
from zones.models import ZoneContextLabel, ZoneRuntimeState


class EventReducer:
    """Stateless event builder driven by prior runtime flags."""

    def __init__(self, policy: EventPolicy) -> None:
        self.policy = policy

    def focus_sustained(self, timestamp: float, temporal_state: TemporalState) -> SceneTransitionEvent:
        return SceneTransitionEvent(
            event_type="focus_sustained",
            timestamp=timestamp,
            description=f"Focused work held for {temporal_state.metrics.focus_duration_seconds:.1f}s",
            scene_label="Focused Work",
        )

    def distraction_started(self, timestamp: float, actor_id: int) -> DistractionEvent:
        return DistractionEvent(
            event_type="distraction_started",
            timestamp=timestamp,
            description=f"Actor {actor_id} shifted into phone-centered behavior",
            actor_id=actor_id,
        )

    def distraction_resolved(self, timestamp: float, actor_id: int) -> DistractionEvent:
        return DistractionEvent(
            event_type="distraction_resolved",
            timestamp=timestamp,
            description=f"Actor {actor_id} resolved the distraction state",
            actor_id=actor_id,
        )

    def focus_resumed(self, timestamp: float, actor_id: int) -> SceneTransitionEvent:
        return SceneTransitionEvent(
            event_type="focus_resumed",
            timestamp=timestamp,
            description=f"Actor {actor_id} returned to laptop-oriented focus",
            actor_id=actor_id,
            scene_label="Focused Work",
        )

    def collaboration_events(
        self,
        timestamp: float,
        features: SceneFeatures,
        temporal_state: TemporalState,
        group_was_active: bool,
    ) -> list[CollaborationEvent]:
        events: list[CollaborationEvent] = []
        group_now = (
            features.multiple_people_clustered
            and features.person_count >= self.policy.group_person_count
        )
        if group_now and not group_was_active:
            events.append(
                CollaborationEvent(
                    event_type="group_formed",
                    timestamp=timestamp,
                    description="A clustered group became visible",
                    scene_label="Group Activity",
                )
            )
        if group_now and (temporal_state.metrics.collaboration_increasing or not group_was_active):
            events.append(
                CollaborationEvent(
                    event_type="collaboration_increasing",
                    timestamp=timestamp,
                    description="Collaboration signals are increasing",
                    scene_label="Group Activity",
                )
            )
        if group_was_active and not group_now:
            events.append(
                CollaborationEvent(
                    event_type="group_dispersed",
                    timestamp=timestamp,
                    description="The clustered group dispersed",
                )
            )
        return events

    def stability_events(self, timestamp: float, temporal_state: TemporalState, unstable_was_active: bool) -> list[StabilityEvent]:
        events: list[StabilityEvent] = []
        if temporal_state.metrics.context_unstable and not unstable_was_active:
            events.append(
                StabilityEvent(
                    event_type="context_unstable",
                    timestamp=timestamp,
                    description="Context became unstable",
                )
            )
        if unstable_was_active and not temporal_state.metrics.context_unstable:
            events.append(
                StabilityEvent(
                    event_type="context_stabilized",
                    timestamp=timestamp,
                    description="Context stabilized again",
                )
            )
        return events

    def active_distraction_ids(self, actor_frame_state: ActorFrameState, temporal_state: TemporalState) -> set[int]:
        if temporal_state.metrics.distraction_score < self.policy.distraction_start_threshold:
            return set()
        return {
            track_id
            for track_id, actor in actor_frame_state.actors.items()
            if actor.interaction_state == "phone_engaged"
        }

    def zone_occupied(self, timestamp: float, zone_state: ZoneRuntimeState) -> ZoneEvent:
        return ZoneEvent(
            event_type="zone_occupied",
            timestamp=timestamp,
            description=f"{zone_state.zone_name} became occupied",
            metadata={"zone_id": zone_state.zone_id, "zone_label": zone_state.context.label.value},
        )

    def zone_cleared(self, timestamp: float, zone_state: ZoneRuntimeState) -> ZoneEvent:
        return ZoneEvent(
            event_type="zone_cleared",
            timestamp=timestamp,
            description=f"{zone_state.zone_name} became empty",
            metadata={"zone_id": zone_state.zone_id, "zone_label": zone_state.context.label.value},
        )

    def zone_focus_started(self, timestamp: float, zone_state: ZoneRuntimeState) -> ZoneEvent:
        return ZoneEvent(
            event_type="zone_focus_started",
            timestamp=timestamp,
            description=f"{zone_state.zone_name} entered solo focus",
            metadata={"zone_id": zone_state.zone_id, "zone_label": ZoneContextLabel.SOLO_FOCUS.value},
        )

    def zone_group_started(self, timestamp: float, zone_state: ZoneRuntimeState) -> ZoneEvent:
        return ZoneEvent(
            event_type="zone_group_started",
            timestamp=timestamp,
            description=f"{zone_state.zone_name} entered group activity",
            metadata={"zone_id": zone_state.zone_id, "zone_label": ZoneContextLabel.GROUP_ACTIVITY.value},
        )
