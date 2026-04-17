"""Profile-specific CLI and startup tests."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import app
from common.models import OverlayMode, SourceMode
from common.profile import ProfilePresentation, RuntimeProfile
from common.config import VisionOSConfig


def test_parse_args_accepts_profile_selection(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.py",
            "--source",
            "video",
            "--input",
            "demo/sample.mp4",
            "--profile",
            "meeting_room",
        ],
    )

    config = app.parse_args()

    assert config.profile_name == "meeting_room"
    assert config.profile_path is None


def test_parse_args_accepts_profile_file_and_tracks_explicit_overrides(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.py",
            "--source",
            "video",
            "--input",
            "demo/sample.mp4",
            "--profile-file",
            "profiles/custom.yaml",
            "--policy",
            "office",
            "--zones-file",
            "config/zones.yaml",
            "--trigger-file",
            "config/triggers.yaml",
            "--overlay-mode",
            "debug",
        ],
    )

    config = app.parse_args()

    assert config.profile_name is None
    assert config.profile_path == "profiles/custom.yaml"
    assert config.policy_explicit is True
    assert config.zones_explicit is True
    assert config.trigger_explicit is True
    assert config.overlay_mode_explicit is True


def test_parse_args_marks_profiled_fields_as_implicit_by_default(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.py",
            "--source",
            "video",
            "--input",
            "demo/sample.mp4",
        ],
    )

    config = app.parse_args()

    assert config.profile_name is None
    assert config.profile_path is None
    assert config.policy_explicit is False
    assert config.zones_explicit is False
    assert config.trigger_explicit is False
    assert config.overlay_mode_explicit is False


def test_apply_profile_defaults_fills_implicit_settings() -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.VIDEO,
        input_path="demo/sample.mp4",
    )
    profile = RuntimeProfile(
        profile_id="meeting_room",
        name="Meeting Room",
        description="Collaboration-first defaults",
        policy_name="office",
        zones_path="/tmp/zones.yaml",
        trigger_path="/tmp/triggers.yaml",
        presentation=ProfilePresentation(overlay_mode=OverlayMode.DEBUG),
    )

    resolved = app._apply_profile_defaults(config, profile)

    assert resolved.policy_name == "office"
    assert resolved.zones_path == "/tmp/zones.yaml"
    assert resolved.trigger_path == "/tmp/triggers.yaml"
    assert resolved.overlay_mode == OverlayMode.DEBUG


def test_apply_profile_defaults_preserves_explicit_settings() -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.VIDEO,
        input_path="demo/sample.mp4",
        policy_name="default",
        zones_path="config/zones.yaml",
        trigger_path="config/triggers.yaml",
        overlay_mode=OverlayMode.COMPACT,
        policy_explicit=True,
        zones_explicit=True,
        trigger_explicit=True,
        overlay_mode_explicit=True,
    )
    profile = RuntimeProfile(
        profile_id="meeting_room",
        name="Meeting Room",
        description="Collaboration-first defaults",
        policy_name="office",
        zones_path="/tmp/zones.yaml",
        trigger_path="/tmp/triggers.yaml",
        presentation=ProfilePresentation(overlay_mode=OverlayMode.DEBUG),
    )

    resolved = app._apply_profile_defaults(config, profile)

    assert resolved.policy_name == "default"
    assert resolved.zones_path == "config/zones.yaml"
    assert resolved.trigger_path == "config/triggers.yaml"
    assert resolved.overlay_mode == OverlayMode.COMPACT


def test_main_applies_profile_defaults_before_validation(monkeypatch) -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.VIDEO,
        input_path="demo/sample.mp4",
        profile_name="meeting_room",
    )
    validated = {}
    profile = RuntimeProfile(
        profile_id="meeting_room",
        name="Meeting Room",
        description="Collaboration-first defaults",
        policy_name="office",
        zones_path="config/zones.yaml",
        trigger_path="config/triggers.yaml",
        presentation=ProfilePresentation(overlay_mode=OverlayMode.DEBUG),
    )

    monkeypatch.setattr(app, "parse_args", lambda: config)
    monkeypatch.setattr(app, "load_profile", lambda name=None, path=None: profile)
    monkeypatch.setattr(app, "_validate_input_path", lambda resolved: validated.setdefault("config", resolved))
    monkeypatch.setattr(app, "load_policy", lambda name, path=None: SimpleNamespace(name=name))
    monkeypatch.setattr(app, "load_zones", lambda path: ())
    monkeypatch.setattr(app, "load_trigger_config", lambda path: "trigger-config")
    monkeypatch.setattr(app, "FrameRenderer", lambda mode: SimpleNamespace(mode=mode))
    monkeypatch.setattr(app, "_build_source", lambda _config: object())
    monkeypatch.setattr(app, "_run_streaming_mode", lambda *_args: 0)
    monkeypatch.setattr(app, "_run_sequential_mode", lambda *_args: 0)

    assert app.main() == 0
    assert validated["config"].policy_name == "office"
    assert validated["config"].zones_path == "config/zones.yaml"
    assert validated["config"].trigger_path == "config/triggers.yaml"
    assert validated["config"].overlay_mode == OverlayMode.DEBUG


def test_main_preserves_explicit_overrides_over_profile_defaults(monkeypatch) -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.VIDEO,
        input_path="demo/sample.mp4",
        profile_name="meeting_room",
        policy_name="default",
        zones_path="custom/zones.yaml",
        trigger_path="custom/triggers.yaml",
        overlay_mode=OverlayMode.COMPACT,
        policy_explicit=True,
        zones_explicit=True,
        trigger_explicit=True,
        overlay_mode_explicit=True,
    )
    profile = RuntimeProfile(
        profile_id="meeting_room",
        name="Meeting Room",
        description="Collaboration-first defaults",
        policy_name="office",
        zones_path="config/zones.yaml",
        trigger_path="config/triggers.yaml",
        presentation=ProfilePresentation(overlay_mode=OverlayMode.DEBUG),
    )
    captured = {}

    def _capture_policy(name, path=None):
        captured["policy_name"] = name
        return SimpleNamespace(name=name)

    def _capture_zones(path):
        captured["zones_path"] = path
        return ()

    def _capture_trigger(path):
        captured["trigger_path"] = path
        return "trigger-config"

    def _capture_renderer(mode):
        captured["overlay_mode"] = mode
        return SimpleNamespace(mode=mode)

    monkeypatch.setattr(app, "parse_args", lambda: config)
    monkeypatch.setattr(app, "load_profile", lambda name=None, path=None: profile)
    monkeypatch.setattr(app, "_validate_input_path", lambda resolved: None)
    monkeypatch.setattr(app, "load_policy", _capture_policy)
    monkeypatch.setattr(app, "load_zones", _capture_zones)
    monkeypatch.setattr(app, "load_trigger_config", _capture_trigger)
    monkeypatch.setattr(app, "FrameRenderer", _capture_renderer)
    monkeypatch.setattr(app, "_build_source", lambda _config: object())
    monkeypatch.setattr(app, "_run_streaming_mode", lambda *_args: 0)
    monkeypatch.setattr(app, "_run_sequential_mode", lambda *_args: 0)

    assert app.main() == 0
    assert captured["policy_name"] == "default"
    assert captured["zones_path"] == "custom/zones.yaml"
    assert captured["trigger_path"] == "custom/triggers.yaml"
    assert captured["overlay_mode"] == OverlayMode.COMPACT
