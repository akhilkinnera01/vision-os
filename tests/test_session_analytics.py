"""Tests for session analytics accumulation and export."""

from __future__ import annotations

import json
from pathlib import Path

from common.models import ContextLabel, HistoryRecord, SessionAnalyticsSummary
from runtime.benchmark import BenchmarkSummary
from runtime.history import SessionAnalyticsEngine


def _record(frame_index: int, timestamp: float, label: str, *, events: tuple[str, ...] = (), stability: float = 0.8) -> HistoryRecord:
    return HistoryRecord(
        frame_index=frame_index,
        timestamp=timestamp,
        scene_label=label,
        confidence=0.9,
        action="observe",
        stability_score=stability,
        event_types=events,
    )


def test_session_analytics_engine_returns_zero_summary_when_empty() -> None:
    summary = SessionAnalyticsEngine().build_summary(BenchmarkSummary())

    assert summary == SessionAnalyticsSummary()


def test_session_analytics_engine_aggregates_event_counts_and_label_durations() -> None:
    engine = SessionAnalyticsEngine()
    engine.add_record(_record(0, 0.0, ContextLabel.FOCUSED_WORK.value, events=("focus_sustained",), stability=0.9))
    engine.add_record(_record(1, 4.0, ContextLabel.FOCUSED_WORK.value, stability=0.8))
    engine.add_record(_record(2, 8.0, ContextLabel.GROUP_ACTIVITY.value, events=("group_formed",), stability=0.7))

    summary = engine.build_summary(
        BenchmarkSummary(
            frames_processed=3,
            fps=10.0,
            average_inference_ms=12.0,
            decision_switch_rate=0.125,
            stage_timings={"detect": 11.0},
        )
    )

    assert summary.frames_processed == 3
    assert summary.event_counts["focus_sustained"] == 1
    assert summary.event_counts["group_formed"] == 1
    assert summary.label_durations[ContextLabel.FOCUSED_WORK.value] == 8.0
    assert summary.label_durations[ContextLabel.GROUP_ACTIVITY.value] == 0.0
    assert summary.focus_duration_seconds == 8.0
    assert summary.decision_switch_count == 1
    assert summary.dominant_scene_label == ContextLabel.FOCUSED_WORK.value
    assert summary.average_stability_score == 0.8


def test_session_analytics_engine_writes_summary_json(tmp_path: Path) -> None:
    engine = SessionAnalyticsEngine()
    engine.add_record(_record(0, 1.0, ContextLabel.CASUAL_USE.value))
    output_path = tmp_path / "analytics" / "summary.json"

    engine.write_summary(
        str(output_path),
        BenchmarkSummary(frames_processed=1, average_inference_ms=9.5),
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["frames_processed"] == 1
    assert payload["average_inference_ms"] == 9.5
