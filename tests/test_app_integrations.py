"""App-level tests for generic integrations wiring."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

import app
from common.config import VisionOSConfig
from common.models import SessionAnalyticsSummary, SourceMode
from common.policy import load_policy


def test_parse_args_accepts_integrations_file(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.py",
            "--source",
            "video",
            "--input",
            "demo/sample.mp4",
            "--integrations-file",
            "config/integrations.yaml",
        ],
    )

    config = app.parse_args()

    assert config.source_mode == SourceMode.VIDEO
    assert config.integrations_path == "config/integrations.yaml"


def test_validate_input_path_rejects_missing_integration_file() -> None:
    config = VisionOSConfig(source_mode=SourceMode.WEBCAM, integrations_path="missing-integrations.yaml")

    with pytest.raises(FileNotFoundError, match="Integration config not found"):
        app._validate_input_path(config)


def test_main_passes_integration_config_and_profile_id_into_sequential_runtime(monkeypatch) -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.VIDEO,
        input_path="demo/sample.mp4",
        integrations_path="config/integrations.yaml",
        profile_name="meeting_room",
        headless=True,
    )
    profile = SimpleNamespace(profile_id="meeting_room")
    captured = {}

    monkeypatch.setattr(app, "parse_args", lambda: config)
    monkeypatch.setattr(app, "_validate_input_path", lambda _config: None)
    monkeypatch.setattr(app, "_load_selected_profile", lambda _config: profile)
    monkeypatch.setattr(app, "_apply_profile_defaults", lambda cfg, _profile: cfg)
    monkeypatch.setattr(app, "load_policy", lambda name, path=None: load_policy(name, path))
    monkeypatch.setattr(app, "load_zones", lambda path: ())
    monkeypatch.setattr(app, "select_zones_for_profile", lambda zones, active_profile=None: zones)
    monkeypatch.setattr(app, "load_trigger_config", lambda path: None)
    monkeypatch.setattr(app, "load_integration_config", lambda path: "integration-config")
    monkeypatch.setattr(app, "FrameRenderer", lambda mode, presentation=None: SimpleNamespace(mode=mode, presentation=presentation))
    monkeypatch.setattr(app, "_build_source", lambda _config: object())
    monkeypatch.setattr(app, "_run_streaming_mode", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(
        app,
        "_run_sequential_mode",
        lambda _config, _policy, _zones, _trigger_config, _source, _renderer, _logger, *, integration_config=None, profile_id=None: captured.update(
            {"integration_config": integration_config, "profile_id": profile_id}
        )
        or 0,
    )

    assert app.main() == 0
    assert captured["integration_config"] == "integration-config"
    assert captured["profile_id"] == "meeting_room"


def test_finalize_run_dispatches_session_summary_integrations() -> None:
    benchmark_tracker = SimpleNamespace(
        summary=lambda: SimpleNamespace(
            frames_processed=12,
            fps=15.0,
            average_inference_ms=20.0,
            dropped_frames=0,
            decision_switch_rate=0.1,
            scene_stability_score=0.9,
            to_dict=lambda: {"frames_processed": 12},
        ),
        write_summary=lambda path: None,
    )
    analytics_engine = SimpleNamespace(
        build_summary=lambda summary: SessionAnalyticsSummary(
            started_at=1.0,
            ended_at=10.0,
            duration_seconds=9.0,
            frames_processed=summary.frames_processed,
            fps=summary.fps,
            average_inference_ms=summary.average_inference_ms,
            dominant_scene_label="Focused Work",
        ),
        write_summary=lambda path, summary: SessionAnalyticsSummary(dominant_scene_label="Focused Work"),
    )
    publisher_calls = []
    publisher = SimpleNamespace(
        publish_session_summary=lambda summary: publisher_calls.append(summary) or ("published",)
    )

    result = app._finalize_run(
        VisionOSConfig(source_mode=SourceMode.REPLAY),
        benchmark_tracker,
        app.VisionLogger(False),
        analytics_engine=analytics_engine,
        integration_publisher=publisher,
    )

    assert result == 0
    assert len(publisher_calls) == 1
    assert publisher_calls[0].dominant_scene_label == "Focused Work"


def test_main_reports_only_enabled_integration_targets_in_startup_summary(monkeypatch) -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.VIDEO,
        input_path="demo/sample.mp4",
        integrations_path="config/integrations.yaml",
        headless=True,
    )
    captured = {}

    monkeypatch.setattr(app, "parse_args", lambda: config)
    monkeypatch.setattr(app, "_validate_input_path", lambda _config: None)
    monkeypatch.setattr(app, "load_policy", lambda name, path=None: load_policy(name, path))
    monkeypatch.setattr(app, "load_zones", lambda path: ())
    monkeypatch.setattr(app, "load_trigger_config", lambda path: None)
    monkeypatch.setattr(
        app,
        "load_integration_config",
        lambda path: SimpleNamespace(
            targets=(
                SimpleNamespace(enabled=True),
                SimpleNamespace(enabled=False),
                SimpleNamespace(enabled=True),
            )
        ),
    )
    monkeypatch.setattr(app, "FrameRenderer", lambda mode, presentation=None: SimpleNamespace(mode=mode, presentation=presentation))
    monkeypatch.setattr(app, "_build_source", lambda _config: object())
    monkeypatch.setattr(
        app,
        "format_startup_summary",
        lambda config, *, policy_name, zone_count, trigger_count, integration_count, profile_id: captured.update(
            {"integration_count": integration_count}
        )
        or "startup",
    )
    monkeypatch.setattr(app, "_run_streaming_mode", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(app, "_run_sequential_mode", lambda *_args, **_kwargs: 0)

    assert app.main() == 0
    assert captured["integration_count"] == 2
