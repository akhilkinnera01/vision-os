"""Tests for app-level run selection and orchestration helpers."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

import app
from common.config import VisionOSConfig
from common.models import ContextLabel, OverlayMode, RuntimeMetrics, SceneMetrics, SourceMode
from common.policy import load_policy
from integrations import TriggeredActionRecord


def test_webcam_uses_streaming_runtime_even_when_headless() -> None:
    config = VisionOSConfig(source_mode=SourceMode.WEBCAM, headless=True)

    assert app._should_use_streaming_runtime(config) is True


def test_video_uses_sequential_runtime() -> None:
    config = VisionOSConfig(source_mode=SourceMode.VIDEO, input_path="demo/sample.mp4")

    assert app._should_use_streaming_runtime(config) is False


def test_main_routes_headless_webcam_through_streaming(monkeypatch) -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.WEBCAM,
        headless=True,
        overlay_mode=OverlayMode.DEBUG,
    )
    calls: list[str] = []

    monkeypatch.setattr(app, "parse_args", lambda: config)
    monkeypatch.setattr(app, "_validate_input_path", lambda _config: None)
    monkeypatch.setattr(app, "load_policy", lambda name, path=None: load_policy(name, path))
    monkeypatch.setattr(app, "FrameRenderer", lambda mode, presentation=None: SimpleNamespace(mode=mode, presentation=presentation))
    monkeypatch.setattr(app, "_build_source", lambda _config: object())
    monkeypatch.setattr(
        app,
        "_run_streaming_mode",
        lambda *_args, **_kwargs: calls.append("streaming") or 0,
    )
    monkeypatch.setattr(
        app,
        "_run_sequential_mode",
        lambda *_args, **_kwargs: calls.append("sequential") or 0,
    )

    assert app.main() == 0
    assert calls == ["streaming"]


def test_parse_args_accepts_zones_file(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.py",
            "--source",
            "video",
            "--input",
            "demo/sample.mp4",
            "--zones-file",
            "config/zones.yaml",
            "--trigger-file",
            "config/triggers.yaml",
        ],
    )

    config = app.parse_args()

    assert config.source_mode == SourceMode.VIDEO
    assert config.zones_path == "config/zones.yaml"
    assert config.trigger_path == "config/triggers.yaml"


def test_validate_input_path_rejects_missing_zones_file() -> None:
    config = VisionOSConfig(source_mode=SourceMode.WEBCAM, zones_path="missing-zones.yaml")

    with pytest.raises(FileNotFoundError, match="Zone config not found"):
        app._validate_input_path(config)


def test_validate_input_path_rejects_missing_trigger_file() -> None:
    config = VisionOSConfig(source_mode=SourceMode.WEBCAM, trigger_path="missing-triggers.yaml")

    with pytest.raises(FileNotFoundError, match="Trigger config not found"):
        app._validate_input_path(config)


def test_main_loads_zone_config_before_running(monkeypatch) -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.WEBCAM,
        headless=True,
        zones_path="config/zones.yaml",
        overlay_mode=OverlayMode.COMPACT,
    )
    calls: list[str] = []

    monkeypatch.setattr(app, "parse_args", lambda: config)
    monkeypatch.setattr(app, "_validate_input_path", lambda _config: None)
    monkeypatch.setattr(app, "load_policy", lambda name, path=None: load_policy(name, path))
    monkeypatch.setattr(app, "load_zones", lambda path: [SimpleNamespace(zone_id="desk_a"), SimpleNamespace(zone_id="desk_b")])
    monkeypatch.setattr(app, "FrameRenderer", lambda mode, presentation=None: SimpleNamespace(mode=mode, presentation=presentation))
    monkeypatch.setattr(app, "_build_source", lambda _config: object())
    monkeypatch.setattr(app, "_run_streaming_mode", lambda *_args, **_kwargs: calls.append("streaming") or 0)
    monkeypatch.setattr(app, "_run_sequential_mode", lambda *_args, **_kwargs: calls.append("sequential") or 0)

    assert app.main() == 0
    assert calls == ["streaming"]


def test_main_passes_trigger_config_into_sequential_runtime(monkeypatch) -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.VIDEO,
        input_path="demo/sample.mp4",
        trigger_path="config/triggers.yaml",
        headless=True,
    )
    captured = {}

    monkeypatch.setattr(app, "parse_args", lambda: config)
    monkeypatch.setattr(app, "_validate_input_path", lambda _config: None)
    monkeypatch.setattr(app, "load_policy", lambda name, path=None: load_policy(name, path))
    monkeypatch.setattr(app, "load_zones", lambda path: ())
    monkeypatch.setattr(app, "load_trigger_config", lambda path: "trigger-config")
    monkeypatch.setattr(app, "FrameRenderer", lambda mode, presentation=None: SimpleNamespace(mode=mode, presentation=presentation))
    monkeypatch.setattr(app, "_build_source", lambda _config: object())
    monkeypatch.setattr(
        app,
        "_run_streaming_mode",
        lambda *_args, **_kwargs: 0,
    )
    monkeypatch.setattr(
        app,
        "_run_sequential_mode",
        lambda _config, _policy, _zones, trigger_config, _source, _renderer, _logger, **_kwargs: captured.update({"trigger_config": trigger_config}) or 0,
    )

    assert app.main() == 0
    assert captured["trigger_config"] == "trigger-config"


def test_main_builds_a_workspace_manifest_for_session_control(monkeypatch) -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.VIDEO,
        input_path="demo/sample.mp4",
        profile_name="meeting_room",
        headless=True,
    )
    captured = {}

    class _Controller:
        def __init__(self) -> None:
            self.active_session = None

        def start_session(self, workspace):
            captured["workspace"] = workspace
            self.active_session = SimpleNamespace(workspace_id=workspace.workspace_id, state="running")
            return self.active_session

        def finish_session(self, final_state: str):
            captured["final_state"] = final_state
            self.active_session = None
            return SimpleNamespace(state=final_state)

    monkeypatch.setattr(app, "SessionController", _Controller)
    monkeypatch.setattr(app, "parse_args", lambda: config)
    monkeypatch.setattr(app, "_validate_input_path", lambda _config: None)
    monkeypatch.setattr(app, "load_policy", lambda name, path=None: load_policy(name, path))
    monkeypatch.setattr(app, "FrameRenderer", lambda mode, presentation=None: SimpleNamespace(mode=mode, presentation=presentation))
    monkeypatch.setattr(app, "_build_source", lambda _config: object())
    monkeypatch.setattr(app, "_load_selected_profile", lambda _config: SimpleNamespace(profile_id="meeting_room"))
    monkeypatch.setattr(app, "_apply_profile_defaults", lambda cfg, _profile: cfg)
    monkeypatch.setattr(app, "_run_streaming_mode", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(app, "_run_sequential_mode", lambda *_args, **_kwargs: 0)

    assert app.main() == 0
    assert captured["workspace"].workspace_id == "meeting_room-video"
    assert captured["workspace"].profile_id == "meeting_room"
    assert captured["workspace"].source_ref == "demo/sample.mp4"
    assert captured["final_state"] == "completed"


def test_run_sequential_mode_records_trigger_records(monkeypatch, tmp_path) -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.VIDEO,
        input_path="demo/sample.mp4",
        record_path=str(tmp_path / "session.jsonl"),
        headless=True,
        max_frames=1,
    )
    packet = SimpleNamespace(
        frame_index=0,
        timestamp=0.0,
        frame=np.zeros((720, 1280, 3), dtype=np.uint8),
    )
    trigger_record = TriggeredActionRecord(
        trigger_id="focus-session",
        action_type="file_append",
        timestamp=0.0,
        target="out/focus.jsonl",
        payload={"trigger_id": "focus-session", "label": "Focused Work"},
        success=True,
    )
    writes: list[dict[str, object]] = []

    class FakeSource:
        def __init__(self) -> None:
            self._packets = [packet]

        def is_opened(self) -> bool:
            return True

        def read(self):
            return self._packets.pop(0) if self._packets else None

        def close(self) -> None:
            pass

    class FakeRecorder:
        def write(self, **kwargs) -> None:
            writes.append(kwargs)

        def close(self) -> None:
            pass

    monkeypatch.setattr(app, "ReplayRecorder", lambda *_args, **_kwargs: FakeRecorder())
    monkeypatch.setattr(
        app,
        "VisionPipeline",
        lambda _config, policy=None, zones=(), trigger_config=None, benchmark_tracker=None, **_kwargs: SimpleNamespace(
            process=lambda _packet: SimpleNamespace(
                detections=[],
                decision=SimpleNamespace(label=ContextLabel.FOCUSED_WORK),
                explanation=SimpleNamespace(),
                runtime_metrics=RuntimeMetrics(frames_processed=1),
                zone_states=(),
                events=[],
                trigger_records=(trigger_record,),
            )
        ),
    )

    result = app._run_sequential_mode(
        config,
        load_policy("default"),
        (),
        "trigger-config",
        FakeSource(),
        SimpleNamespace(),
        app.VisionLogger(False),
    )

    assert result == 0
    assert writes[0]["trigger_records"] == (trigger_record,)


def test_run_sequential_mode_records_history_records(monkeypatch, tmp_path) -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.VIDEO,
        input_path="demo/sample.mp4",
        history_output_path=str(tmp_path / "history.jsonl"),
        session_summary_output_path=str(tmp_path / "session-summary.json"),
        headless=True,
        max_frames=1,
    )
    packet = SimpleNamespace(
        frame_index=0,
        timestamp=0.0,
        frame=np.zeros((720, 1280, 3), dtype=np.uint8),
    )
    history_record = SimpleNamespace(frame_index=0, scene_label="Focused Work")
    history_writes = []
    summaries = []

    class FakeSource:
        def __init__(self) -> None:
            self._packets = [packet]

        def is_opened(self) -> bool:
            return True

        def read(self):
            return self._packets.pop(0) if self._packets else None

        def close(self) -> None:
            pass

    class FakeHistoryRecorder:
        def write(self, record) -> None:
            history_writes.append(record)

        def close(self) -> None:
            pass

    class FakeAnalyticsEngine:
        def add_record(self, record) -> None:
            summaries.append(("record", record))

        def write_summary(self, output_path, benchmark_summary) -> None:
            summaries.append(("summary", output_path, benchmark_summary))

    monkeypatch.setattr(app, "HistoryRecorder", lambda *_args, **_kwargs: FakeHistoryRecorder(), raising=False)
    monkeypatch.setattr(app, "SessionAnalyticsEngine", lambda: FakeAnalyticsEngine(), raising=False)
    monkeypatch.setattr(
        app,
        "VisionPipeline",
        lambda _config, policy=None, zones=(), trigger_config=None, benchmark_tracker=None, **_kwargs: SimpleNamespace(
            process=lambda _packet: SimpleNamespace(
                detections=[],
                decision=SimpleNamespace(label=ContextLabel.FOCUSED_WORK),
                explanation=SimpleNamespace(),
                runtime_metrics=RuntimeMetrics(frames_processed=1),
                zone_states=(),
                events=[],
                trigger_records=(),
                history_record=history_record,
            )
        ),
    )

    result = app._run_sequential_mode(
        config,
        load_policy("default"),
        (),
        None,
        FakeSource(),
        SimpleNamespace(),
        app.VisionLogger(False),
    )

    assert result == 0
    assert history_writes == [history_record]
    assert summaries[0] == ("record", history_record)
    assert summaries[1][0] == "summary"


def test_finalize_run_logs_history_and_session_summary_artifacts(tmp_path) -> None:
    tracker = app.BenchmarkTracker()
    tracker.record_inference(0.0, 12.0, ContextLabel.FOCUSED_WORK)
    captured = []

    class FakeLogger:
        def log(self, event: str, **kwargs) -> None:
            captured.append((event, kwargs))

    class FakeAnalyticsEngine:
        def build_summary(self, benchmark_summary):
            return SimpleNamespace(
                dominant_scene_label="Focused Work",
                event_counts={"focus_sustained": 2, "distraction_started": 1},
                focus_duration_seconds=12.0,
            )

        def write_summary(self, output_path, benchmark_summary) -> None:
            Path(output_path).write_text("{}", encoding="utf-8")

    config = VisionOSConfig(
        source_mode=SourceMode.VIDEO,
        history_output_path=str(tmp_path / "history.jsonl"),
        session_summary_output_path=str(tmp_path / "session-summary.json"),
    )

    result = app._finalize_run(config, tracker, FakeLogger(), analytics_engine=FakeAnalyticsEngine())

    assert result == 0
    assert any(event == "artifact_written" and payload["kind"] == "history" for event, payload in captured)
    assert any(event == "artifact_written" and payload["kind"] == "session_summary" for event, payload in captured)
    assert any(
        event == "run_completed"
        and payload["dominant_scene_label"] == "Focused Work"
        and payload["total_event_count"] == 3
        and payload["focus_duration_seconds"] == 12.0
        for event, payload in captured
    )
