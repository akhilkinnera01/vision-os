"""Temporal memory and sliding-window scene state aggregation."""

from __future__ import annotations

from collections import Counter, deque
from statistics import mean

from common.models import ContextLabel, SceneFeatures, SceneMetrics, TemporalSnapshot, TemporalState


class TemporalMemory:
    """Track a short history of feature snapshots to infer scene behavior over time."""

    def __init__(self, window_seconds: float = 8.0) -> None:
        self.window_seconds = max(1.0, window_seconds)
        self._history: deque[TemporalSnapshot] = deque()

    def update(
        self,
        timestamp: float,
        features: SceneFeatures,
        label: ContextLabel,
        confidence: float,
    ) -> TemporalState:
        """Append a sample and derive windowed scene metrics from recent history."""
        self._history.append(
            TemporalSnapshot(
                timestamp=timestamp,
                label=label,
                confidence=confidence,
                features=features,
            )
        )
        self._trim(timestamp)

        if not self._history:
            return TemporalState()

        labels = [snapshot.label for snapshot in self._history]
        label_counts = Counter(labels)
        dominant_label, _ = label_counts.most_common(1)[0]
        window_span = max(0.0, self._history[-1].timestamp - self._history[0].timestamp)
        switch_count = sum(
            1 for index in range(1, len(labels)) if labels[index] != labels[index - 1]
        )
        switch_rate = switch_count / max(window_span, 1.0)
        dominant_duration = self._run_duration_for_label(dominant_label)
        focus_duration = self._run_duration_for_label(ContextLabel.FOCUSED_WORK)

        focus_values = [self._normalize_focus(snapshot.features) for snapshot in self._history]
        distraction_values = [
            self._normalize_distraction(snapshot.features) for snapshot in self._history
        ]
        collaboration_values = [
            self._normalize_collaboration(snapshot.features) for snapshot in self._history
        ]

        focus_score = min(1.0, focus_values[-1] * 0.65 + min(focus_duration / 8.0, 1.0) * 0.35)
        distraction_baseline = mean(distraction_values[:-1]) if len(distraction_values) > 1 else 0.0
        distraction_spike = distraction_values[-1] > distraction_baseline + 0.22
        distraction_score = min(
            1.0,
            distraction_values[-1] + (0.15 if distraction_spike else 0.0),
        )

        collaboration_now = collaboration_values[-1]
        early_collaboration = mean(collaboration_values[:-1]) if len(collaboration_values) > 1 else 0.0
        collaboration_increasing = collaboration_now > early_collaboration + 0.18
        collaboration_score = min(
            1.0,
            collaboration_now + (0.12 if collaboration_increasing else 0.0),
        )

        label_agreement = label_counts[dominant_label] / len(self._history)
        confidence_average = mean(snapshot.confidence for snapshot in self._history)
        stability_score = max(0.0, min(1.0, label_agreement * 0.7 + confidence_average * 0.3 - min(switch_rate / 4.0, 0.4)))
        context_unstable = stability_score < 0.5 or switch_count >= 3

        notes: list[str] = []
        if dominant_duration > 0:
            notes.append(f"{dominant_label.value} for {dominant_duration:.1f}s")
        if distraction_spike:
            notes.append("Phone distraction spike")
        if collaboration_increasing:
            notes.append("Collaboration likely increasing")
        if context_unstable:
            notes.append("Context unstable")

        metrics = SceneMetrics(
            focus_score=round(focus_score, 3),
            distraction_score=round(distraction_score, 3),
            collaboration_score=round(collaboration_score, 3),
            stability_score=round(stability_score, 3),
            focus_duration_seconds=round(focus_duration, 2),
            decision_switch_rate=round(switch_rate, 3),
            distraction_spike=distraction_spike,
            collaboration_increasing=collaboration_increasing,
            context_unstable=context_unstable,
        )
        return TemporalState(
            window_span_seconds=round(window_span, 2),
            dominant_label=dominant_label,
            dominant_duration_seconds=round(dominant_duration, 2),
            label_switch_count=switch_count,
            notes=notes,
            metrics=metrics,
        )

    def _trim(self, timestamp: float) -> None:
        cutoff = timestamp - self.window_seconds
        while self._history and self._history[0].timestamp < cutoff:
            self._history.popleft()

    def _run_duration_for_label(self, label: ContextLabel) -> float:
        relevant: list[TemporalSnapshot] = []
        for snapshot in reversed(self._history):
            if snapshot.label != label:
                break
            relevant.append(snapshot)
        if not relevant:
            return 0.0
        if len(relevant) == 1:
            return 0.0
        return relevant[0].timestamp - relevant[-1].timestamp

    def _normalize_focus(self, features: SceneFeatures) -> float:
        return min(
            1.0,
            0.22 * features.person_count
            + min(features.workspace_score / 3.0, 0.55)
            + (0.15 if features.laptop_near_person else 0.0)
            + (0.1 if features.centered_monitor else 0.0)
            + min(features.desk_like_score, 0.18),
        )

    def _normalize_distraction(self, features: SceneFeatures) -> float:
        return min(
            1.0,
            min(features.casual_score / 3.0, 0.55)
            + (0.2 if features.phone_near_person else 0.0)
            + min(features.room_like_score, 0.2),
        )

    def _normalize_collaboration(self, features: SceneFeatures) -> float:
        return min(
            1.0,
            min(features.collaboration_score / 3.0, 0.6)
            + (0.2 if features.multiple_people_clustered else 0.0)
            + 0.05 * min(features.person_count, 4),
        )
