"""JSON-log coverage for session analytics completion records."""

from __future__ import annotations

import json
from types import SimpleNamespace

import app
from common.config import VisionOSConfig
from common.models import ContextLabel, SourceMode
from telemetry.logging import VisionLogger


def test_finalize_run_json_logs_include_session_analytics(capsys) -> None:
    tracker = app.BenchmarkTracker()
    tracker.record_inference(0.0, 11.0, ContextLabel.CASUAL_USE)

    class _AnalyticsEngine:
        def build_summary(self, benchmark_summary):
            return SimpleNamespace(
                dominant_scene_label="Casual Use",
                event_counts={"zone_occupied": 1, "zone_cleared": 1},
                focus_duration_seconds=0.0,
            )

    result = app._finalize_run(
        VisionOSConfig(source_mode=SourceMode.VIDEO),
        tracker,
        VisionLogger(json_mode=True),
        analytics_engine=_AnalyticsEngine(),
    )

    assert result == 0
    payload = json.loads(capsys.readouterr().err)
    assert payload["event"] == "run_completed"
    assert payload["dominant_scene_label"] == "Casual Use"
    assert payload["total_event_count"] == 2
