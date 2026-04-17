"""Tests for structured session history records and summaries."""

from __future__ import annotations

from common.models import HistoryRecord, SessionAnalyticsSummary


def test_history_record_round_trip() -> None:
    record = HistoryRecord(
        frame_index=7,
        timestamp=12.5,
        scene_label="Focused Work",
        confidence=0.91,
        action="Enable productivity-oriented monitoring",
        risk_flags=("context unstable",),
        focus_score=0.81,
        distraction_score=0.22,
        collaboration_score=0.14,
        stability_score=0.88,
        focus_duration_seconds=10.0,
        decision_switch_rate=0.125,
        average_inference_ms=23.4,
        fps=11.7,
        dropped_frames=1,
        event_types=("focus_sustained", "zone_focus_started"),
        trigger_ids=("workstation-focus-log",),
        zone_labels={"desk_a": "solo_focus"},
        stage_timings={"detect": 22.9, "event": 0.01},
    )

    restored = HistoryRecord.from_dict(record.to_dict())

    assert restored == record


def test_session_analytics_summary_round_trip() -> None:
    summary = SessionAnalyticsSummary(
        started_at=0.0,
        ended_at=12.0,
        duration_seconds=12.0,
        frames_processed=8,
        fps=13.7,
        average_inference_ms=22.6,
        dropped_frames=0,
        dominant_scene_label="Focused Work",
        decision_switch_count=1,
        decision_switch_rate=0.083,
        average_stability_score=0.84,
        focus_duration_seconds=8.0,
        group_activity_duration_seconds=2.0,
        casual_use_duration_seconds=2.0,
        event_counts={"focus_sustained": 1, "zone_focus_started": 1},
        label_durations={"Focused Work": 8.0, "Group Activity": 2.0, "Casual Use": 2.0},
        stage_timings={"detect": 22.1, "event": 0.02},
    )

    restored = SessionAnalyticsSummary.from_dict(summary.to_dict())

    assert restored == summary
