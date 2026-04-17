"""Tests for append-only session history export."""

from __future__ import annotations

import json
from pathlib import Path

from common.models import HistoryRecord
from runtime.history import HistoryRecorder


def test_history_recorder_writes_jsonl_records(tmp_path: Path) -> None:
    output_path = tmp_path / "history" / "session.jsonl"
    recorder = HistoryRecorder(str(output_path))
    recorder.write(
        HistoryRecord(
            frame_index=3,
            timestamp=1.25,
            scene_label="Focused Work",
            confidence=0.91,
            action="observe",
            event_types=("focus_sustained",),
        )
    )
    recorder.close()

    payload = json.loads(output_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["frame_index"] == 3
    assert payload["event_types"] == ["focus_sustained"]


def test_history_recorder_creates_parent_directories(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "analytics" / "history.jsonl"
    recorder = HistoryRecorder(str(output_path))
    recorder.write(
        HistoryRecord(
            frame_index=0,
            timestamp=0.0,
            scene_label="Casual Use",
            confidence=0.5,
            action="observe",
        )
    )
    recorder.close()

    assert output_path.is_file()
