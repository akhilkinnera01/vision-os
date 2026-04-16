"""Generate concise human-readable reasoning for the current frame."""

from __future__ import annotations

from common.models import Decision, Explanation, SceneContext, SceneFeatures


class ExplanationEngine:
    """Render decision data into one readable sentence for the overlay."""

    def explain(
        self,
        decision: Decision,
        scene_context: SceneContext,
        features: SceneFeatures,
    ) -> Explanation:
        """Summarize why the system chose the current scene label."""
        lead_signal = scene_context.signals[0] if scene_context.signals else "scene cues are limited"
        return Explanation(
            summary=(
                f"{decision.label.value}: {lead_signal}; "
                f"people={features.person_count}, "
                f"workspace={features.workspace_score:.1f}, "
                f"casual={features.casual_score:.1f}."
            )
        )
