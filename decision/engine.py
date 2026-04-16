"""Turn inferred context into a stable, action-oriented decision."""

from __future__ import annotations

from common.models import ContextLabel, Decision, SceneContext, SceneFeatures


class DecisionEngine:
    """Policy layer that adds light hysteresis to avoid flickering labels."""

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

    def decide(self, scene_context: SceneContext, features: SceneFeatures) -> Decision:
        """Produce a stable classification and action suggestion."""
        chosen_label = self._stabilize_label(scene_context.label)
        reasoning_facts = list(scene_context.signals)
        reasoning_facts.append(f"workspace score={features.workspace_score:.1f}")
        reasoning_facts.append(f"casual score={features.casual_score:.1f}")

        return Decision(
            label=chosen_label,
            confidence=scene_context.confidence,
            action=self.ACTION_MAP.get(chosen_label, "Keep observing"),
            reasoning_facts=reasoning_facts,
        )

    def _stabilize_label(self, proposed_label: ContextLabel) -> ContextLabel:
        """Require a short confirmation streak before switching scene labels."""
        if self._active_label is None:
            self._active_label = proposed_label
            self._candidate_label = None
            self._candidate_hits = 0
            return proposed_label

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
