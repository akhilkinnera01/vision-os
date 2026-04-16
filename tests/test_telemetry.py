"""Tests for stage telemetry and worker health."""

from __future__ import annotations

import pytest

from common.models import ContextLabel
from runtime.benchmark import BenchmarkTracker
from telemetry.health import HealthMonitor, WorkerFailure
from telemetry.timers import StageTimer


def test_stage_timer_records_named_blocks() -> None:
    timer = StageTimer()
    with timer.measure("detect"):
        pass

    snapshot = timer.snapshot()
    assert "detect" in snapshot
    assert snapshot["detect"] >= 0.0


def test_benchmark_tracker_aggregates_stage_timings() -> None:
    tracker = BenchmarkTracker()
    tracker.record_inference(
        0.0,
        12.0,
        ContextLabel.FOCUSED_WORK,
        stage_timings={"detect": 6.0, "track": 2.0},
    )
    runtime_metrics = tracker.record_inference(
        1.0,
        18.0,
        ContextLabel.FOCUSED_WORK,
        stage_timings={"detect": 8.0, "track": 4.0},
        scene_stability_score=0.72,
    )
    summary = tracker.summary()

    assert runtime_metrics.stage_timings["detect"] == 7.0
    assert summary.stage_timings["track"] == 3.0
    assert summary.scene_stability_score == 0.72


def test_health_monitor_raises_worker_failures() -> None:
    monitor = HealthMonitor()
    monitor.report_exception(stage="track", exc=RuntimeError("assignment failed"))

    with pytest.raises(WorkerFailure, match="track"):
        monitor.raise_if_unhealthy()
