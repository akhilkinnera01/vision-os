"""Tests for the Easy Setup demo preset."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import app
from common.models import OverlayMode, SourceMode


DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"


def test_parse_args_accepts_demo_mode(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["app.py", "--demo"])

    config = app.parse_args()

    assert config.demo_mode is True
    assert config.source_mode == SourceMode.REPLAY
    assert config.input_path == str(DEMO_DIR / "demo-replay.jsonl")
    assert config.profile_path == str(DEMO_DIR / "sample-profile.yaml")


def test_parse_args_preserves_explicit_overrides_over_demo(monkeypatch) -> None:
    video_path = DEMO_DIR / "sample.mp4"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.py",
            "--demo",
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


def test_demo_mode_writes_history_and_summary_artifacts(monkeypatch, tmp_path: Path) -> None:
    history_path = tmp_path / "history.jsonl"
    summary_path = tmp_path / "session-summary.json"
    benchmark_path = tmp_path / "benchmark.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.py",
            "--demo",
            "--headless",
            "--max-frames",
            "5",
            "--history-output",
            str(history_path),
            "--session-summary-output",
            str(summary_path),
            "--benchmark-output",
            str(benchmark_path),
        ],
    )

    result = app.main()

    assert result == 0
    history_lines = history_path.read_text(encoding="utf-8").splitlines()
    assert len(history_lines) == 5
    assert json.loads(history_lines[0])["scene_label"]

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["frames_processed"] == 5

    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    assert benchmark["frames_processed"] == 5


def test_config_driven_demo_run_uses_committed_setup_manifest(monkeypatch, tmp_path: Path) -> None:
    benchmark_path = tmp_path / "benchmark.json"
    history_path = tmp_path / "history.jsonl"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.py",
            "--config",
            str(DEMO_DIR / "demo-setup-config.yaml"),
            "--max-frames",
            "4",
            "--benchmark-output",
            str(benchmark_path),
            "--history-output",
            str(history_path),
        ],
    )

    result = app.main()

    assert result == 0
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    assert benchmark["frames_processed"] == 4
    assert len(history_path.read_text(encoding="utf-8").splitlines()) == 4
