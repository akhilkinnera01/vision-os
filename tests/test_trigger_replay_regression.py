"""Replay-first regression coverage for the trigger engine."""

from __future__ import annotations

from pathlib import Path

from common.config import VisionOSConfig
from common.models import BoundingBox, Detection, SourceMode
from common.policy import load_policy
from integrations import load_trigger_config
from runtime.io import ReplayFrameSource, ReplayRecorder
from runtime.pipeline import VisionPipeline


def _detection(label: str, bbox: tuple[int, int, int, int]) -> Detection:
    box = BoundingBox(*bbox)
    return Detection(
        label=label,
        confidence=0.91,
        bbox=box,
        area_ratio=box.area / float(1280 * 720),
    )


def test_replay_fixture_produces_expected_trigger_sequence(tmp_path: Path) -> None:
    trigger_path = tmp_path / "triggers.yaml"
    trigger_path.write_text(
        """
triggers:
  - id: focus-sustained
    when:
      source: decision.label
      operator: equals
      value: Focused Work
      min_duration_seconds: 5
    then:
      - type: file_append
        path: out/focus.jsonl
""".strip(),
        encoding="utf-8",
    )
    replay_path = tmp_path / "session.jsonl"
    recorder = ReplayRecorder(str(replay_path), source_mode=SourceMode.VIDEO)
    detections = [
        _detection("person", (80, 80, 180, 320)),
        _detection("laptop", (120, 240, 260, 330)),
        _detection("keyboard", (110, 320, 290, 380)),
    ]
    for frame_index, timestamp in enumerate((0.0, 4.0, 5.0, 9.0)):
        recorder.write(
            frame_index=frame_index,
            timestamp=timestamp,
            frame_shape=(720, 1280),
            detections=detections,
        )
    recorder.close()

    pipeline = VisionPipeline(
        VisionOSConfig(source_mode=SourceMode.REPLAY),
        policy=load_policy("default"),
        trigger_config=load_trigger_config(str(trigger_path)),
    )
    source = ReplayFrameSource(str(replay_path))

    emitted_trigger_ids: list[str] = []
    emitted_timestamps: list[float] = []
    while True:
        packet = source.read()
        if packet is None:
            break
        output = pipeline.process(packet)
        for record in output.trigger_records:
            emitted_trigger_ids.append(record.trigger_id)
            emitted_timestamps.append(record.timestamp)
    source.close()

    assert emitted_trigger_ids == ["focus-sustained"]
    assert emitted_timestamps == [5.0]
