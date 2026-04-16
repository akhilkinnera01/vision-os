"""Infer a high-level scene context from the extracted features."""

from __future__ import annotations

from common.policy import DecisionPolicy
from common.models import ContextLabel, SceneContext, SceneFeatures, TemporalState


class ContextRulesEngine:
    """Rule-based context inference that is easy to extend or replace."""

    def __init__(self, decision_policy: DecisionPolicy | None = None) -> None:
        self.decision_policy = decision_policy or DecisionPolicy()

    def infer(self, features: SceneFeatures, temporal_state: TemporalState | None = None) -> SceneContext:
        """Map feature combinations to a scene label and supporting signals."""
        signals: list[str] = []
        temporal_metrics = temporal_state.metrics if temporal_state else None

        if features.person_count >= 2:
            signals.append(f"{features.person_count} people are visible")
        elif features.person_count == 1:
            signals.append("a single person is visible")

        if features.laptop_near_person:
            signals.append("laptop is close to the active person")
        if features.phone_near_person:
            signals.append("phone is close to the active person")
        if features.focused_person_count:
            signals.append(f"{features.focused_person_count} tracked person is laptop-engaged")
        if features.distracted_person_count:
            signals.append(f"{features.distracted_person_count} tracked person is phone-engaged")
        if features.multiple_people_clustered:
            signals.append("multiple people are clustered")
        if features.centered_monitor:
            signals.append("monitor is dominant near the center")
        if features.desk_like_score >= 0.45:
            signals.append("scene looks desk-like")
        if features.room_like_score >= 0.45:
            signals.append("scene looks room-like")

        focus_score = min(
            1.0,
            min(features.workspace_score / 3.0, 0.65)
            + (0.18 if features.laptop_near_person else 0.0)
            + min(features.focused_person_count * 0.08, 0.16)
            + min(features.desk_like_score, 0.2),
        )
        collaboration_score = min(
            1.0,
            min(features.collaboration_score / 3.0, 0.6)
            + (0.2 if features.multiple_people_clustered else 0.0),
        )
        casual_score = min(
            1.0,
            min(features.casual_score / 3.0, 0.6)
            + (0.18 if features.phone_near_person else 0.0)
            + min(features.distracted_person_count * 0.1, 0.2)
            + min(features.room_like_score, 0.18),
        )

        if temporal_metrics is not None:
            focus_score = focus_score * 0.7 + temporal_metrics.focus_score * 0.3
            collaboration_score = collaboration_score * 0.75 + temporal_metrics.collaboration_score * 0.25
            casual_score = casual_score * 0.75 + temporal_metrics.distraction_score * 0.25
            signals.extend(note for note in temporal_state.notes if note not in signals)

        if features.person_count >= 2 and collaboration_score >= max(focus_score, casual_score) - 0.02:
            label = ContextLabel.GROUP_ACTIVITY
            confidence = min(0.98, 0.55 + collaboration_score * 0.4)
            confidence_reason = "Multiple nearby people and collaboration cues dominate the window."
        elif focus_score >= casual_score + self.decision_policy.focus_margin and focus_score >= collaboration_score - 0.05:
            label = ContextLabel.FOCUSED_WORK
            confidence = min(0.97, 0.52 + focus_score * 0.43)
            confidence_reason = "Work objects and person-device proximity outweigh distraction cues."
        else:
            label = ContextLabel.CASUAL_USE
            confidence = min(0.94, 0.5 + casual_score * 0.4)
            confidence_reason = "Distraction or room-level cues outweigh sustained work evidence."

        if temporal_metrics is not None and temporal_metrics.context_unstable:
            confidence = max(0.45, confidence - self.decision_policy.unstable_confidence_penalty)

        return SceneContext(
            label=label,
            confidence=round(confidence, 3),
            signals=signals[:5] if signals else [f"{features.dominant_label} is the strongest cue in view"],
            confidence_reason=confidence_reason,
        )
