"""Tests for Easy Setup config manifests and CLI config loading."""

from __future__ import annotations

from pathlib import Path
import sys

import app
from common.config import VisionOSConfig
from common.models import OverlayMode, SourceMode
from setupux.config_file import load_runtime_config_file, write_runtime_config_file


def test_load_runtime_config_file_resolves_relative_paths(tmp_path: Path) -> None:
    replay_path = tmp_path / "session.jsonl"
    replay_path.write_text("{}\n", encoding="utf-8")
    zones_path = tmp_path / "visionos.zones.yaml"
    zones_path.write_text("zones: []\n", encoding="utf-8")
    triggers_path = tmp_path / "visionos.triggers.yaml"
    triggers_path.write_text("triggers: []\n", encoding="utf-8")
    config_path = tmp_path / "visionos.config.yaml"
    config_path.write_text(
        """
source: replay
input: session.jsonl
profile: workstation
policy: office
overlay_mode: debug
headless: true
zones_file: visionos.zones.yaml
trigger_file: visionos.triggers.yaml
benchmark_output: out/benchmark.json
history_output: out/history.jsonl
session_summary_output: out/session-summary.json
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_runtime_config_file(str(config_path))

    assert config.source_mode == SourceMode.REPLAY
    assert config.input_path == str(replay_path)
    assert config.profile_name == "workstation"
    assert config.policy_name == "office"
    assert config.overlay_mode == OverlayMode.DEBUG
    assert config.headless is True
    assert config.zones_path == str(zones_path)
    assert config.trigger_path == str(triggers_path)
    assert config.benchmark_output_path == str(tmp_path / "out" / "benchmark.json")
    assert config.history_output_path == str(tmp_path / "out" / "history.jsonl")
    assert config.session_summary_output_path == str(tmp_path / "out" / "session-summary.json")


def test_write_runtime_config_file_persists_integrations_path_relatively(tmp_path: Path) -> None:
    integrations_path = tmp_path / "visionos.integrations.yaml"
    integrations_path.write_text("integrations: []\n", encoding="utf-8")
    config_path = tmp_path / "visionos.config.yaml"

    write_runtime_config_file(
        VisionOSConfig(
            source_mode=SourceMode.REPLAY,
            input_path=str(tmp_path / "session.jsonl"),
            integrations_path=str(integrations_path),
            overlay_mode=OverlayMode.DEBUG,
        ),
        str(config_path),
    )

    payload = config_path.read_text(encoding="utf-8")

    assert "integrations_file: visionos.integrations.yaml" in payload


def test_parse_args_accepts_config_file(monkeypatch, tmp_path: Path) -> None:
    replay_path = tmp_path / "session.jsonl"
    replay_path.write_text("{}\n", encoding="utf-8")
    config_path = tmp_path / "visionos.config.yaml"
    config_path.write_text(
        """
source: replay
input: session.jsonl
overlay_mode: debug
profile: workstation
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(sys, "argv", ["app.py", "--config", str(config_path)])

    config = app.parse_args()

    assert config.source_mode == SourceMode.REPLAY
    assert config.input_path == str(replay_path)
    assert config.overlay_mode == OverlayMode.DEBUG
    assert config.profile_name == "workstation"


def test_parse_args_preserves_explicit_overrides_over_config_file(monkeypatch, tmp_path: Path) -> None:
    replay_path = tmp_path / "session.jsonl"
    replay_path.write_text("{}\n", encoding="utf-8")
    video_path = tmp_path / "sample.mp4"
    video_path.write_text("video", encoding="utf-8")
    config_path = tmp_path / "visionos.config.yaml"
    config_path.write_text(
        """
source: replay
input: session.jsonl
overlay_mode: debug
profile: workstation
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.py",
            "--config",
            str(config_path),
            "--source",
            "video",
            "--input",
            str(video_path),
            "--overlay-mode",
            "compact",
        ],
    )

    config = app.parse_args()

    assert config.source_mode == SourceMode.VIDEO
    assert config.input_path == str(video_path)
    assert config.overlay_mode == OverlayMode.COMPACT
    assert config.profile_name == "workstation"
