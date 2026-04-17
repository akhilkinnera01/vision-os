"""Tests for replay export compatibility with session history."""

from __future__ import annotations

from pathlib import Path

from common.models import Detection, BoundingBox, HistoryRecord, ReplayRecord, SourceMode
from runtime.io import ReplayFrameSource, ReplayRecorder


def _detection() -> Detection:
    return Detection(
        label="person",
        confidence=0.91,
        bbox=BoundingBox(10, 20, 110, 220),
        area_ratio=0.1,
    )


def test_replay_record_round_trip_preserves_history_record() -> None:
    record = ReplayRecord(
        frame_index=2,
        timestamp=1.5,
        frame_shape=(720, 1280),
        detections=[_detection()],
        source_mode=SourceMode.VIDEO,
        history_record=HistoryRecord(
            frame_index=2,
            timestamp=1.5,
            scene_label="Focused Work",
            confidence=0.88,
            action="Enable productivity-oriented monitoring",
            event_types=("focus_sustained",),
        ),
    )

    restored = ReplayRecord.from_dict(record.to_dict())

    assert restored.history_record == record.history_record


def test_replay_record_from_dict_keeps_old_payloads_compatible() -> None:
    restored = ReplayRecord.from_dict(
        {
            "frame_index": 1,
            "timestamp": 0.5,
            "frame_shape": [720, 1280],
            "detections": [_detection().to_dict()],
            "source_mode": "video",
            "events": [],
            "zone_states": [],
            "trigger_records": [],
        }
    )

    assert restored.history_record is None


def test_replay_recorder_and_source_preserve_history_record(tmp_path: Path) -> None:
    output_path = tmp_path / "session.jsonl"
    recorder = ReplayRecorder(str(output_path), source_mode=SourceMode.VIDEO)
    recorder.write(
        frame_index=2,
        timestamp=1.5,
        frame_shape=(720, 1280),
        detections=[_detection()],
        history_record=HistoryRecord(
            frame_index=2,
            timestamp=1.5,
            scene_label="Focused Work",
            confidence=0.88,
            action="observe",
            event_types=("focus_sustained",),
        ),
    )
    recorder.close()

    source = ReplayFrameSource(str(output_path))
    packet = source.read()
    source.close()

    assert packet is not None
    assert packet.replay_history_record is not None
    assert packet.replay_history_record["scene_label"] == "Focused Work"
