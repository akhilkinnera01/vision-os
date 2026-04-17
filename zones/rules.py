"""Infer zone-local context labels from zone feature sets."""

from __future__ import annotations

from zones.models import ZoneContext, ZoneContextLabel, ZoneFeatureSet, ZoneTemporalState


class ZoneRulesEngine:
    """Map zone-local features into small, stable operational labels."""

    def infer(self, feature_set: ZoneFeatureSet, temporal_state: ZoneTemporalState | None = None) -> ZoneContext:
        features = feature_set.features
        signals: list[str] = []

        if features.person_count >= 2:
            signals.append(f"{features.person_count} people are in the zone")
        elif features.person_count == 1:
            signals.append("one person is in the zone")

        if features.laptop_near_person:
            signals.append("laptop is near the active person")
        if features.phone_near_person:
            signals.append("phone is near the active person")
        if features.multiple_people_clustered:
            signals.append("people are clustered together")

        if features.person_count == 0 and not feature_set.occupied:
            label = ZoneContextLabel.EMPTY
            confidence = 0.94
            reason = "No people or assigned detections are active in the zone."
        elif features.person_count >= 2 and (
            features.multiple_people_clustered or features.collaboration_score >= 0.65
        ):
            label = ZoneContextLabel.GROUP_ACTIVITY
            confidence = min(0.97, 0.55 + min(features.collaboration_score / 3.0, 0.42))
            reason = "Multiple nearby people and collaboration cues dominate the zone."
        elif features.person_count == 1 and (
            features.laptop_near_person
            or features.focused_person_count > 0
            or features.workspace_score >= 0.85
        ):
            label = ZoneContextLabel.SOLO_FOCUS
            confidence = min(0.96, 0.54 + min(features.workspace_score / 3.0, 0.38))
            reason = "A single person and work-oriented cues dominate the zone."
        elif features.person_count > 0 and features.casual_score >= max(features.workspace_score, 0.7):
            label = ZoneContextLabel.CASUAL_OCCUPANCY
            confidence = min(0.92, 0.5 + min(features.casual_score / 3.0, 0.36))
            reason = "People are present, but casual or distraction cues outweigh work cues."
        else:
            label = ZoneContextLabel.OCCUPIED
            confidence = 0.82
            reason = "The zone is occupied without strong focus or collaboration dominance."

        if temporal_state is not None and temporal_state.notes:
            signals.extend(note for note in temporal_state.notes if note not in signals)
            confidence = max(0.45, min(0.98, confidence * 0.75 + temporal_state.stability_score * 0.25))

        return ZoneContext(
            label=label,
            confidence=round(confidence, 3),
            signals=tuple(signals[:5]),
            confidence_reason=reason,
        )
