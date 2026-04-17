"""Tests for setup-era startup UX in app.py."""

from __future__ import annotations

from types import SimpleNamespace

import app
from common.config import VisionOSConfig
from common.models import SourceMode


def test_main_prints_startup_summary_before_running(monkeypatch, capsys) -> None:
    config = VisionOSConfig(
        config_path="demo/demo-setup-config.yaml",
        source_mode=SourceMode.VIDEO,
        input_path="demo/sample.mp4",
        profile_name="meeting_room",
        benchmark_output_path="out/benchmark.json",
        history_output_path="out/history.jsonl",
        session_summary_output_path="out/session-summary.json",
        headless=True,
    )

    monkeypatch.setattr(app, "parse_args", lambda: config)
    monkeypatch.setattr(app, "_load_selected_profile", lambda _config: None)
    monkeypatch.setattr(app, "_validate_input_path", lambda _config: None)
    monkeypatch.setattr(app, "load_policy", lambda name, path=None: SimpleNamespace(name=name))
    monkeypatch.setattr(app, "FrameRenderer", lambda mode, presentation=None: SimpleNamespace(mode=mode, presentation=presentation))
    monkeypatch.setattr(app, "_build_source", lambda _config: object())
    monkeypatch.setattr(app, "_run_streaming_mode", lambda *_args: 0)
    monkeypatch.setattr(app, "_run_sequential_mode", lambda *_args: 0)

    assert app.main() == 0

    captured = capsys.readouterr()
    assert "Startup summary" in captured.out
    assert "Config: demo/demo-setup-config.yaml" in captured.out
    assert "Source: video(demo/sample.mp4)" in captured.out
    assert "Zones: 0 loaded" in captured.out
    assert "Triggers: 0 enabled" in captured.out
