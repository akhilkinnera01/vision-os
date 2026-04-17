"""Replay-first regression coverage for history and analytics exports."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import app


DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"


def test_replay_mode_writes_history_and_summary_artifacts(monkeypatch, tmp_path: Path) -> None:
    history_path = tmp_path / "history.jsonl"
    summary_path = tmp_path / "session-summary.json"
    benchmark_path = tmp_path / "benchmark.json"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.py",
            "--source",
            "replay",
            "--input",
            str(DEMO_DIR / "demo-replay.jsonl"),
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
    assert "dominant_scene_label" in summary

    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    assert benchmark["frames_processed"] == 5
