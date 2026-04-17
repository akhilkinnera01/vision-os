"""Turn zone context into zone-local actions."""

from __future__ import annotations

from zones.models import ZoneContext, ZoneContextLabel, ZoneDecision, ZoneTemporalState


class ZoneDecisionEngine:
    """Produce a downstream action from a zone-local context."""

    def decide(self, context: ZoneContext, temporal_state: ZoneTemporalState | None = None) -> ZoneDecision:
        if temporal_state is not None and temporal_state.stability_score < 0.45:
            return ZoneDecision(
                label=context.label,
                confidence=max(0.4, context.confidence - 0.12),
                action="Hold zone label until state stabilizes",
                reasoning_facts=context.signals,
            )

        action = {
            ZoneContextLabel.EMPTY: "Mark zone available",
            ZoneContextLabel.OCCUPIED: "Keep zone marked as occupied",
            ZoneContextLabel.SOLO_FOCUS: "Preserve focus-friendly zone state",
            ZoneContextLabel.GROUP_ACTIVITY: "Flag collaborative use in the zone",
            ZoneContextLabel.CASUAL_OCCUPANCY: "Monitor casual occupancy",
        }[context.label]
        return ZoneDecision(
            label=context.label,
            confidence=context.confidence,
            action=action,
            reasoning_facts=context.signals,
        )
