"""Tests for pipeline-emitted structured session history."""

from __future__ import annotations

import numpy as np

from common.config import VisionOSConfig
from common.models import BoundingBox, Detection, SourceMode
from common.policy import load_policy
from runtime.io import FramePacket
from runtime.pipeline import VisionPipeline


def _detection(label: str, bbox: tuple[int, int, int, int]) -> Detection:
    box = BoundingBox(*bbox)
    return Detection(
        label=label,
        confidence=0.9,
        bbox=box,
        area_ratio=box.area / float(1280 * 720),
    )


def test_pipeline_emits_history_record_from_stable_output() -> None:
    pipeline = VisionPipeline(
        VisionOSConfig(source_mode=SourceMode.REPLAY, temporal_window_seconds=8.0),
        policy=load_policy("default"),
    )
    packet = FramePacket(
        frame_index=4,
        timestamp=8.0,
        frame=np.zeros((720, 1280, 3), dtype=np.uint8),
        source_mode=SourceMode.REPLAY,
        replay_detections=[
            _detection("person", (220, 120, 420, 620)),
            _detection("laptop", (380, 360, 640, 560)),
            _detection("keyboard", (340, 520, 660, 640)),
        ],
    )

    output = pipeline.process(packet)

    assert output.history_record.frame_index == 4
    assert output.history_record.timestamp == 8.0
    assert output.history_record.scene_label == output.decision.label.value
    assert output.history_record.event_types == tuple(event.event_type for event in output.events)
