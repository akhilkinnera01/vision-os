"""Tests for app-level run selection and orchestration helpers."""

from __future__ import annotations

from types import SimpleNamespace

import app
from common.config import VisionOSConfig
from common.models import OverlayMode, SourceMode
from common.policy import load_policy


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
    monkeypatch.setattr(app, "FrameRenderer", lambda mode: SimpleNamespace(mode=mode))
    monkeypatch.setattr(app, "_build_source", lambda _config: object())
    monkeypatch.setattr(
        app,
        "_run_streaming_mode",
        lambda *_args: calls.append("streaming") or 0,
    )
    monkeypatch.setattr(
        app,
        "_run_sequential_mode",
        lambda *_args: calls.append("sequential") or 0,
    )

    assert app.main() == 0
    assert calls == ["streaming"]
