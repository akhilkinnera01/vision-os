"""Generate structured human-readable reasoning for the current frame."""

from __future__ import annotations

from common.models import Decision, Explanation, RuntimeMetrics, SceneContext, SceneFeatures, TemporalState


class ExplanationEngine:
    """Render decision data into structured compact and debug content."""

    def explain(
        self,
        decision: Decision,
        scene_context: SceneContext,
        features: SceneFeatures,
        temporal_state: TemporalState,
        runtime_metrics: RuntimeMetrics,
    ) -> Explanation:
        """Summarize why the system chose the current scene label."""
        top_signals = list(scene_context.signals[:3]) or ["scene cues are limited"]
        scores = {
            "focus": round(decision.scene_metrics.focus_score, 3),
            "distraction": round(decision.scene_metrics.distraction_score, 3),
            "collaboration": round(decision.scene_metrics.collaboration_score, 3),
            "stability": round(decision.scene_metrics.stability_score, 3),
        }

        compact_summary = (
            f"{decision.label.value} | focus {scores['focus']:.2f} | "
            f"distraction {scores['distraction']:.2f} | stability {scores['stability']:.2f}"
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
        )
