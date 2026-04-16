"""Infer a high-level scene context from the extracted features."""

from __future__ import annotations

from common.models import ContextLabel, SceneContext, SceneFeatures


class ContextRulesEngine:
    """Rule-based context inference that is easy to extend or replace."""

    def infer(self, features: SceneFeatures) -> SceneContext:
        """Map feature combinations to a scene label and supporting signals."""
        signals: list[str] = []

        if features.person_count >= 2:
            signals.append(f"{features.person_count} people are visible")
        elif features.person_count == 1:
            signals.append("a single person is visible")

        if features.has_laptop:
            signals.append("a laptop is present")
        if features.has_keyboard:
            signals.append("a keyboard is visible")
        if features.has_phone:
            signals.append("a phone is present")

        if features.person_count >= 2 and features.collaboration_score >= 2.0:
            confidence = min(0.99, 0.65 + 0.08 * features.person_count)
            return SceneContext(
                label=ContextLabel.GROUP_ACTIVITY,
                confidence=confidence,
                signals=signals or ["multiple people suggest collaboration"],
            )

        if features.person_count >= 1 and features.workspace_score >= 1.6:
            confidence = min(0.96, 0.55 + 0.1 * features.workspace_score)
            return SceneContext(
                label=ContextLabel.FOCUSED_WORK,
                confidence=confidence,
                signals=signals or ["work-oriented objects dominate the frame"],
            )

        confidence = min(0.9, 0.5 + 0.08 * max(features.casual_score, 1.0))
        fallback_signals = signals or [f"{features.dominant_label} is the strongest cue in view"]
        return SceneContext(
            label=ContextLabel.CASUAL_USE,
            confidence=confidence,
            signals=fallback_signals,
        )
