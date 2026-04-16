"""Turn inferred context into a stable, action-oriented decision."""

from __future__ import annotations

from common.models import ContextLabel, Decision, SceneContext, SceneFeatures, TemporalState


class DecisionEngine:
    """Policy layer that keeps the final scene label stable and actionable."""

    ACTION_MAP = {
        ContextLabel.FOCUSED_WORK: "Enable productivity-oriented monitoring",
        ContextLabel.CASUAL_USE: "Stay in passive observation mode",
        ContextLabel.GROUP_ACTIVITY: "Highlight collaborative activity",
    }

    def __init__(self, switch_confirmations: int = 2) -> None:
        self.switch_confirmations = max(1, switch_confirmations)
        self._active_label: ContextLabel | None = None
        self._candidate_label: ContextLabel | None = None
        self._candidate_hits = 0

    def decide(
        self,
        scene_context: SceneContext,
        features: SceneFeatures,
        temporal_state: TemporalState,
    ) -> Decision:
        """Produce a stable classification and action suggestion."""
        chosen_label = self._stabilize_label(scene_context.label, temporal_state.metrics.context_unstable)
        action = self._choose_action(chosen_label, temporal_state)

        reasoning_facts = list(scene_context.signals[:3])
        if temporal_state.notes:
            reasoning_facts.extend(temporal_state.notes[:2])

        risk_flags: list[str] = []
        if temporal_state.metrics.context_unstable:
            risk_flags.append("Context unstable")
        if temporal_state.metrics.distraction_spike:
            risk_flags.append("Distraction spike")
        if features.phone_near_person:
            risk_flags.append("Phone near person")

        return Decision(
            label=chosen_label,
            confidence=scene_context.confidence,
            action=action,
            reasoning_facts=reasoning_facts,
            risk_flags=risk_flags,
            scene_metrics=temporal_state.metrics,
        )

    def _choose_action(self, label: ContextLabel, temporal_state: TemporalState) -> str:
        if temporal_state.metrics.distraction_spike:
            return "Flag short distraction event"
        if temporal_state.metrics.collaboration_increasing:
            return "Escalate collaboration watch"
        if temporal_state.metrics.context_unstable:
            return "Hold current label until context stabilizes"
        return self.ACTION_MAP.get(label, "Keep observing")

    def _stabilize_label(self, proposed_label: ContextLabel, context_unstable: bool) -> ContextLabel:
        """Require a short confirmation streak before switching scene labels."""
        if self._active_label is None:
            self._active_label = proposed_label
            self._candidate_label = None
            self._candidate_hits = 0
            return proposed_label

        if context_unstable:
            return self._active_label

        if proposed_label == self._active_label:
            self._candidate_label = None
            self._candidate_hits = 0
            return self._active_label

        if proposed_label != self._candidate_label:
            self._candidate_label = proposed_label
            self._candidate_hits = 1
            return self._active_label

        self._candidate_hits += 1
        if self._candidate_hits >= self.switch_confirmations:
            self._active_label = proposed_label
            self._candidate_label = None
            self._candidate_hits = 0

        return self._active_label
