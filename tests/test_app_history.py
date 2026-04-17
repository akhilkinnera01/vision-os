"""Tests for event history and analytics CLI wiring."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import app
from common.models import ContextLabel
from common.config import VisionOSConfig
from common.models import SourceMode


def test_parse_args_accepts_history_output_flags(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.py",
            "--source",
            "video",
            "--input",
            "demo/sample.mp4",
            "--history-output",
            "out/history.jsonl",
            "--session-summary-output",
            "out/session-summary.json",
        ],
    )

    config = app.parse_args()

    assert config.history_output_path == "out/history.jsonl"
    assert config.session_summary_output_path == "out/session-summary.json"


def test_log_run_started_includes_history_artifact_paths() -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.VIDEO,
        input_path="demo/sample.mp4",
        history_output_path="out/history.jsonl",
        session_summary_output_path="out/session-summary.json",
    )
    captured = {}

    class _Logger:
        def log(self, event: str, **kwargs) -> None:
            captured["event"] = event
            captured["kwargs"] = kwargs

    app._log_run_started(config, "default", 0, _Logger())

    assert captured["event"] == "run_started"
    assert captured["kwargs"]["history_output_path"] == "out/history.jsonl"
    assert captured["kwargs"]["session_summary_output_path"] == "out/session-summary.json"


def test_main_passes_history_artifact_paths_to_runtime(monkeypatch) -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.VIDEO,
        input_path="demo/sample.mp4",
        history_output_path="out/history.jsonl",
        session_summary_output_path="out/session-summary.json",
        headless=True,
    )
    captured = {}

    monkeypatch.setattr(app, "parse_args", lambda: config)
    monkeypatch.setattr(app, "_load_selected_profile", lambda _config: None)
    monkeypatch.setattr(app, "_validate_input_path", lambda _config: None)
    monkeypatch.setattr(app, "load_policy", lambda name, path=None: SimpleNamespace(name=name))
    monkeypatch.setattr(app, "FrameRenderer", lambda mode, presentation=None: SimpleNamespace(mode=mode, presentation=presentation))
    monkeypatch.setattr(app, "_build_source", lambda _config: object())
    monkeypatch.setattr(app, "_run_streaming_mode", lambda *_args, **_kwargs: 0)

    def _capture_run(runtime_config, *_args, **_kwargs):
        captured["config"] = runtime_config
        return 0

    monkeypatch.setattr(
        app,
        "_run_sequential_mode",
        _capture_run,
    )

    assert app.main() == 0
    assert captured["config"].history_output_path == "out/history.jsonl"
    assert captured["config"].session_summary_output_path == "out/session-summary.json"


def test_finalize_run_logs_analytics_even_without_summary_output() -> None:
    tracker = app.BenchmarkTracker()
    tracker.record_inference(0.0, 10.0, ContextLabel.CASUAL_USE)
    captured = []

    class _Logger:
        def log(self, event: str, **kwargs) -> None:
            captured.append((event, kwargs))

    class _AnalyticsEngine:
        def build_summary(self, benchmark_summary):
            return SimpleNamespace(
                dominant_scene_label="Casual Use",
                event_counts={"zone_occupied": 2},
                focus_duration_seconds=0.0,
            )

    result = app._finalize_run(
        VisionOSConfig(source_mode=SourceMode.VIDEO),
        tracker,
        _Logger(),
        analytics_engine=_AnalyticsEngine(),
    )

    assert result == 0
    assert any(
        event == "run_completed"
        and payload["dominant_scene_label"] == "Casual Use"
        and payload["total_event_count"] == 2
        for event, payload in captured
    )
