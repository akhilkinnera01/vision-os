"""Pipeline and replay integration tests for generic integration records."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from common.config import VisionOSConfig
from common.models import BoundingBox, Detection, SourceMode
from common.policy import load_policy
from integrations import DispatchRecord, IntegrationConfig, IntegrationTarget, load_trigger_config
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


def test_pipeline_emits_integration_records_for_trigger_and_status_targets(tmp_path: Path) -> None:
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
        integration_config=IntegrationConfig(
            targets=(
                IntegrationTarget(
                    integration_id="status-log",
                    target_type="file_append",
                    source="status",
                    target=str(tmp_path / "status.jsonl"),
                    interval_seconds=5.0,
                ),
                IntegrationTarget(
                    integration_id="trigger-log",
                    target_type="file_append",
                    source="trigger",
                    target=str(tmp_path / "trigger-events.jsonl"),
                    trigger_ids=("focus-session",),
                ),
            )
        ),
        profile_id="meeting_room",
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

    assert [record.integration_id for record in first.integration_records] == ["trigger-log", "status-log"]
    assert second.integration_records == ()
    assert (tmp_path / "trigger-events.jsonl").is_file()
    assert (tmp_path / "status.jsonl").is_file()


def test_replay_record_round_trip_preserves_integration_records(tmp_path: Path) -> None:
    output_path = tmp_path / "session.jsonl"
    recorder = ReplayRecorder(str(output_path), source_mode=SourceMode.VIDEO)
    recorder.write(
        frame_index=2,
        timestamp=4.5,
        frame_shape=(720, 1280),
        detections=[_detection("person", (0, 0, 100, 200))],
        integration_records=(
            DispatchRecord(
                integration_id="status-log",
                target_type="file_append",
                source="status",
                timestamp=4.5,
                target="out/status.jsonl",
                payload={"source": "status", "payload": {"scene_label": "Focused Work"}},
                success=True,
            ),
        ),
    )
    recorder.close()

    source = ReplayFrameSource(str(output_path))
    packet = source.read()
    source.close()

    assert packet is not None
    assert packet.replay_integration_records is not None
    assert packet.replay_integration_records[0]["integration_id"] == "status-log"
