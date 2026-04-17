"""Profile-specific CLI and startup tests."""

from __future__ import annotations

import sys

import app


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
