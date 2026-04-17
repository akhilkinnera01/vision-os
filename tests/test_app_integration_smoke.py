"""Smoke coverage for app-level generic integrations."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import app


DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"


def test_replay_run_writes_status_and_session_summary_integration_outputs(monkeypatch, tmp_path: Path) -> None:
    status_path = tmp_path / "status.jsonl"
    summary_dispatch_path = tmp_path / "session-summary-dispatch.jsonl"
    integration_path = tmp_path / "integrations.yaml"
    integration_path.write_text(
        f"""
integrations:
  - id: status-log
    type: file_append
    source: status
    interval_seconds: 0.1
    path: {status_path}

  - id: session-summary-log
    type: file_append
    source: session_summary
    path: {summary_dispatch_path}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "app.py",
            "--source",
            "replay",
            "--input",
            str(DEMO_DIR / "demo-replay.jsonl"),
            "--integrations-file",
            str(integration_path),
            "--headless",
            "--max-frames",
            "4",
        ],
    )

    result = app.main()

    assert result == 0
    status_lines = status_path.read_text(encoding="utf-8").splitlines()
    summary_lines = summary_dispatch_path.read_text(encoding="utf-8").splitlines()

    assert status_lines
    assert summary_lines

    status_payload = json.loads(status_lines[0])
    summary_payload = json.loads(summary_lines[0])

    assert status_payload["source"] == "status"
    assert status_payload["payload"]["scene_label"]
    assert summary_payload["source"] == "session_summary"
    assert summary_payload["payload"]["dominant_scene_label"]
