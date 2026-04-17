"""Profile-specific CLI and startup tests."""

from __future__ import annotations

import sys

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
