"""Generate structured human-readable reasoning for the current frame."""

from __future__ import annotations

from common.models import (
    Decision,
    Explanation,
    RuntimeMetrics,
    SceneContext,
    SceneFeatures,
    TemporalState,
    VisionEvent,
)
from zones.models import ZoneRuntimeState


class ExplanationEngine:
    """Render decision data into structured compact and debug content."""

    def explain(
        self,
        decision: Decision,
        scene_context: SceneContext,
        features: SceneFeatures,
        temporal_state: TemporalState,
        runtime_metrics: RuntimeMetrics,
        events: list[VisionEvent] | None = None,
        zone_states: tuple[ZoneRuntimeState, ...] = (),
    ) -> Explanation:
        """Summarize why the system chose the current scene label."""
        top_signals = list(scene_context.signals[:3]) or ["scene cues are limited"]
        recent_event_types = [event.event_type for event in (events or [])]
        zone_summaries = [
            f"{zone_state.zone_name}={zone_state.context.label.value}"
            for zone_state in zone_states[:4]
        ]
        scores = {
            "focus": round(decision.scene_metrics.focus_score, 3),
            "distraction": round(decision.scene_metrics.distraction_score, 3),
            "collaboration": round(decision.scene_metrics.collaboration_score, 3),
            "stability": round(decision.scene_metrics.stability_score, 3),
        }

        compact_summary = (
            scene_context.confidence_reason
            if scene_context.confidence_reason
            else f"Top signals: {', '.join(top_signals[:2])}"
        )
        debug_lines = [
            f"Top signals: {', '.join(top_signals)}",
            f"Action: {decision.action}",
            f"Confidence reason: {scene_context.confidence_reason}",
            f"Temporal notes: {', '.join(temporal_state.notes) if temporal_state.notes else 'none'}",
            (
                "Scores: "
                f"focus={scores['focus']:.2f}, distraction={scores['distraction']:.2f}, "
                f"collaboration={scores['collaboration']:.2f}, stability={scores['stability']:.2f}"
            ),
            (
                "Runtime: "
                f"fps={runtime_metrics.fps:.2f}, avg={runtime_metrics.average_inference_ms:.1f}ms, "
                f"dropped={runtime_metrics.dropped_frames}"
            ),
            (
                "Events: "
                f"{', '.join(recent_event_types) if recent_event_types else 'none'}"
            ),
            (
                "Zones: "
                f"{', '.join(zone_summaries) if zone_summaries else 'none'}"
            ),
            (
                "Spatial: "
                f"laptop_near_person={features.laptop_near_person}, "
                f"phone_near_person={features.phone_near_person}, "
                f"people_clustered={features.multiple_people_clustered}"
            ),
        ]
        return Explanation(
            scene_label=decision.label.value,
            top_signals=top_signals,
            risk_flags=decision.risk_flags,
            action=decision.action,
            confidence_reason=scene_context.confidence_reason,
            compact_summary=compact_summary,
            debug_lines=debug_lines,
            scores=scores,
            recent_events=recent_event_types,
            zone_summaries=zone_summaries,
        )
