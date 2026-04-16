"""Benchmark helpers for runtime performance and delivery metrics."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

from common.models import ContextLabel, RuntimeMetrics


@dataclass(slots=True)
class BenchmarkSummary:
    """Final benchmark output emitted at the end of a run."""

    frames_processed: int = 0
    fps: float = 0.0
    average_inference_ms: float = 0.0
    dropped_frames: int = 0
    decision_switch_rate: float = 0.0
    scene_stability_score: float = 0.0
    stage_timings: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


class BenchmarkTracker:
    """Collect runtime metrics without coupling the app loop to a specific UI path."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._frames_processed = 0
        self._dropped_frames = 0
        self._total_inference_ms = 0.0
        self._first_timestamp: float | None = None
        self._last_timestamp: float | None = None
        self._last_label: ContextLabel | None = None
        self._switch_count = 0
        self._scene_stability_score = 0.0
        self._stage_total_ms: dict[str, float] = {}

    def note_dropped_frame(self) -> None:
        with self._lock:
            self._dropped_frames += 1

    def record_inference(
        self,
        timestamp: float,
        inference_ms: float,
        label: ContextLabel,
        stage_timings: dict[str, float] | None = None,
        scene_stability_score: float = 0.0,
    ) -> RuntimeMetrics:
        with self._lock:
            self._frames_processed += 1
            self._total_inference_ms += inference_ms
            self._scene_stability_score = scene_stability_score
            if self._first_timestamp is None:
                self._first_timestamp = timestamp
            self._last_timestamp = timestamp
            if self._last_label is not None and self._last_label != label:
                self._switch_count += 1
            self._last_label = label
            if stage_timings:
                for stage_name, value in stage_timings.items():
                    self._stage_total_ms[stage_name] = self._stage_total_ms.get(stage_name, 0.0) + value
            return self.snapshot()

    def snapshot(self) -> RuntimeMetrics:
        span = max((self._last_timestamp or 0.0) - (self._first_timestamp or 0.0), 1e-6)
        fps = self._frames_processed / span if self._frames_processed > 1 else 0.0
        average_inference_ms = (
            self._total_inference_ms / self._frames_processed if self._frames_processed else 0.0
        )
        stage_timings = {
            stage_name: round(total_ms / self._frames_processed, 3)
            for stage_name, total_ms in self._stage_total_ms.items()
            if self._frames_processed
        }
        return RuntimeMetrics(
            frames_processed=self._frames_processed,
            fps=round(fps, 3),
            average_inference_ms=round(average_inference_ms, 3),
            dropped_frames=self._dropped_frames,
            scene_stability_score=round(self._scene_stability_score, 3),
            stage_timings=stage_timings,
        )

    def summary(self) -> BenchmarkSummary:
        span = max((self._last_timestamp or 0.0) - (self._first_timestamp or 0.0), 1e-6)
        metrics = self.snapshot()
        return BenchmarkSummary(
            frames_processed=metrics.frames_processed,
            fps=metrics.fps,
            average_inference_ms=metrics.average_inference_ms,
            dropped_frames=metrics.dropped_frames,
            decision_switch_rate=round(self._switch_count / span if self._frames_processed > 1 else 0.0, 3),
            scene_stability_score=metrics.scene_stability_score,
            stage_timings=metrics.stage_timings,
        )

    def write_summary(self, output_path: str) -> None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as output_file:
            json.dump(self.summary().to_dict(), output_file, indent=2)
