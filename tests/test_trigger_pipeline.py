"""Pipeline and replay integration tests for trigger records."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from common.config import VisionOSConfig
from common.models import BoundingBox, Detection, SourceMode
from common.policy import load_policy
from integrations import TriggeredActionRecord, load_trigger_config
from runtime.io import FramePacket, ReplayFrameSource, ReplayRecorder
from runtime.pipeline import VisionPipeline


def _detection(label: str, bbox: tuple[int, int, int, int]) -> Detection:
    box = BoundingBox(*bbox)
    return Detection(
        label=label,
        confidence=0.92,
        bbox=box,
        area_ratio=box.area / float(1280 * 720),
    )


def test_pipeline_emits_trigger_records_from_decision_snapshot(tmp_path: Path) -> None:
    trigger_path = tmp_path / "triggers.yaml"
    trigger_path.write_text(
        """
triggers:
  - id: focus-session
    when:
      source: decision.label
      operator: equals
      value: Focused Work
    then:
      - type: file_append
        path: out/focus.jsonl
""".strip(),
        encoding="utf-8",
    )
    pipeline = VisionPipeline(
        VisionOSConfig(source_mode=SourceMode.REPLAY),
        policy=load_policy("default"),
        trigger_config=load_trigger_config(str(trigger_path)),
    )
    detections = [
        _detection("person", (150, 120, 320, 620)),
        _detection("laptop", (300, 360, 600, 560)),
        _detection("keyboard", (280, 520, 630, 650)),
    ]
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)

    first = pipeline.process(
        FramePacket(
            frame_index=0,
            timestamp=0.0,
            frame=frame,
            source_mode=SourceMode.REPLAY,
            replay_detections=detections,
        )
    )
    second = pipeline.process(
        FramePacket(
            frame_index=1,
            timestamp=1.0,
            frame=frame,
            source_mode=SourceMode.REPLAY,
            replay_detections=detections,
        )
    )

    assert len(first.trigger_records) == 1
    assert first.trigger_records[0].trigger_id == "focus-session"
    assert second.trigger_records == ()


def test_replay_record_round_trip_preserves_trigger_records(tmp_path: Path) -> None:
    output_path = tmp_path / "session.jsonl"
    recorder = ReplayRecorder(str(output_path), source_mode=SourceMode.VIDEO)
    recorder.write(
        frame_index=2,
        timestamp=4.5,
        frame_shape=(720, 1280),
        detections=[_detection("person", (0, 0, 100, 200))],
        trigger_records=(
            TriggeredActionRecord(
                trigger_id="focus-session",
                action_type="file_append",
                timestamp=4.5,
                target="out/focus.jsonl",
                payload={"trigger_id": "focus-session", "label": "Focused Work"},
                success=True,
            ),
        ),
    )
    recorder.close()

    source = ReplayFrameSource(str(output_path))
    packet = source.read()
    source.close()

    assert packet is not None
    assert packet.replay_trigger_records is not None
    assert packet.replay_trigger_records[0]["trigger_id"] == "focus-session"
