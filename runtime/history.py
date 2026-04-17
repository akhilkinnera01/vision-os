"""Session history analytics helpers."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from statistics import mean

from common.models import HistoryRecord, SessionAnalyticsSummary
from runtime.benchmark import BenchmarkSummary


class HistoryRecorder:
    """Write append-only session history records as JSONL."""

    def __init__(self, output_path: str) -> None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        self._file = output.open("w", encoding="utf-8")

    def write(self, record: HistoryRecord) -> None:
        self._file.write(json.dumps(record.to_dict()) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


class SessionAnalyticsEngine:
    """Accumulate structured history records into one session summary."""

    def __init__(self) -> None:
        self._records: list[HistoryRecord] = []

    def add_record(self, record: HistoryRecord) -> None:
        self._records.append(record)

    def build_summary(self, benchmark_summary: BenchmarkSummary) -> SessionAnalyticsSummary:
        if not self._records:
            return SessionAnalyticsSummary()

        started_at = self._records[0].timestamp
        ended_at = self._records[-1].timestamp
        label_durations: dict[str, float] = {}
        switch_count = 0
        for current, nxt in zip(self._records, self._records[1:]):
            label_durations[current.scene_label] = round(
                label_durations.get(current.scene_label, 0.0) + max(0.0, nxt.timestamp - current.timestamp),
                3,
            )
            if current.scene_label != nxt.scene_label:
                switch_count += 1
        if self._records[-1].scene_label not in label_durations:
            label_durations[self._records[-1].scene_label] = 0.0

        event_counts = Counter(
            event_type
            for record in self._records
            for event_type in record.event_types
        )
        dominant_scene_label = max(
            label_durations,
            key=lambda label: (label_durations[label], -next(index for index, record in enumerate(self._records) if record.scene_label == label)),
        )
        return SessionAnalyticsSummary(
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=round(max(0.0, ended_at - started_at), 3),
            frames_processed=benchmark_summary.frames_processed,
            fps=benchmark_summary.fps,
            average_inference_ms=benchmark_summary.average_inference_ms,
            dropped_frames=benchmark_summary.dropped_frames,
            dominant_scene_label=dominant_scene_label,
            decision_switch_count=switch_count,
            decision_switch_rate=benchmark_summary.decision_switch_rate,
            average_stability_score=round(mean(record.stability_score for record in self._records), 3),
            focus_duration_seconds=label_durations.get("Focused Work", 0.0),
            group_activity_duration_seconds=label_durations.get("Group Activity", 0.0),
            casual_use_duration_seconds=label_durations.get("Casual Use", 0.0),
            event_counts=dict(event_counts),
            label_durations=label_durations,
            stage_timings=benchmark_summary.stage_timings,
        )

    def write_summary(self, output_path: str, benchmark_summary: BenchmarkSummary) -> None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as handle:
            json.dump(self.build_summary(benchmark_summary).to_dict(), handle, indent=2)
