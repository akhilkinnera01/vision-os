"""Per-zone temporal memory and stability scoring."""

from __future__ import annotations

from collections import Counter, defaultdict, deque

from zones.models import ZoneContext, ZoneContextLabel, ZoneFeatureSet, ZoneTemporalSnapshot, ZoneTemporalState


class ZoneTemporalMemory:
    """Track short rolling state windows independently for each zone."""

    def __init__(self, window_seconds: float = 8.0) -> None:
        self.window_seconds = max(1.0, window_seconds)
        self._history: dict[str, deque[ZoneTemporalSnapshot]] = defaultdict(deque)

    def update(
        self,
        timestamp: float,
        feature_sets: tuple[ZoneFeatureSet, ...],
        contexts: dict[str, ZoneContext],
    ) -> dict[str, ZoneTemporalState]:
        states: dict[str, ZoneTemporalState] = {}
        for feature_set in feature_sets:
            context = contexts[feature_set.zone_id]
            history = self._history[feature_set.zone_id]
            history.append(
                ZoneTemporalSnapshot(
                    timestamp=timestamp,
                    label=context.label,
                    occupied=feature_set.occupied,
                )
            )
            self._trim(history, timestamp)
            states[feature_set.zone_id] = self._summarize(history)
        return states

    def _trim(self, history: deque[ZoneTemporalSnapshot], timestamp: float) -> None:
        cutoff = timestamp - self.window_seconds
        while history and history[0].timestamp < cutoff:
            history.popleft()

    def _summarize(self, history: deque[ZoneTemporalSnapshot]) -> ZoneTemporalState:
        if not history:
            return ZoneTemporalState()

        labels = [snapshot.label for snapshot in history]
        dominant_label, dominant_count = Counter(labels).most_common(1)[0]
        window_span = max(0.0, history[-1].timestamp - history[0].timestamp)
        switch_count = sum(1 for index in range(1, len(labels)) if labels[index] != labels[index - 1])
        stability_score = max(0.0, min(1.0, (dominant_count / len(history)) - min(switch_count * 0.15, 0.45)))
        current_label_duration = self._run_duration(history, history[-1].label)
        occupied_duration = self._occupied_duration(history)

        notes: list[str] = []
        if current_label_duration > 0:
            notes.append(f"{history[-1].label.value} for {current_label_duration:.1f}s")
        if switch_count >= 3:
            notes.append("zone context unstable")
        if occupied_duration > 0:
            notes.append(f"occupied for {occupied_duration:.1f}s")

        return ZoneTemporalState(
            window_span_seconds=round(window_span, 2),
            dominant_label=dominant_label,
            current_label_duration_seconds=round(current_label_duration, 2),
            occupied_duration_seconds=round(occupied_duration, 2),
            label_switch_count=switch_count,
            stability_score=round(stability_score, 3),
            notes=tuple(notes),
        )

    def _run_duration(self, history: deque[ZoneTemporalSnapshot], label: ZoneContextLabel) -> float:
        relevant: list[ZoneTemporalSnapshot] = []
        for snapshot in reversed(history):
            if snapshot.label != label:
                break
            relevant.append(snapshot)
        if len(relevant) < 2:
            return 0.0
        return relevant[0].timestamp - relevant[-1].timestamp

    def _occupied_duration(self, history: deque[ZoneTemporalSnapshot]) -> float:
        relevant: list[ZoneTemporalSnapshot] = []
        for snapshot in reversed(history):
            if not snapshot.occupied:
                break
            relevant.append(snapshot)
        if len(relevant) < 2:
            return 0.0
        return relevant[0].timestamp - relevant[-1].timestamp
