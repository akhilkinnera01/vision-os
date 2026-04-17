"""Replay-first regression coverage for zone-aware reasoning."""

from __future__ import annotations

from pathlib import Path

from common.config import VisionOSConfig
from common.models import BoundingBox, Detection, SourceMode
from common.policy import load_policy
from runtime.io import ReplayFrameSource, ReplayRecorder
from runtime.pipeline import VisionPipeline
from zones import load_zones


def _detection(label: str, bbox: tuple[int, int, int, int]) -> Detection:
    box = BoundingBox(*bbox)
    return Detection(
        label=label,
        confidence=0.91,
        bbox=box,
        area_ratio=box.area / float(1280 * 720),
    )


def test_zone_replay_regression_tracks_focus_timeline(tmp_path: Path) -> None:
    zones_path = tmp_path / "zones.yaml"
    zones_path.write_text(
        """
zones:
  - id: desk_a
    name: Desk A
    type: occupancy
    polygon:
      - [0, 0]
      - [420, 0]
      - [420, 420]
      - [0, 420]
""".strip(),
        encoding="utf-8",
    )
    replay_path = tmp_path / "focus-zone.jsonl"
    recorder = ReplayRecorder(str(replay_path), source_mode=SourceMode.VIDEO)
    detections = [
        _detection("person", (80, 80, 180, 320)),
        _detection("laptop", (120, 240, 260, 330)),
    ]
    for frame_index, timestamp in enumerate((0.0, 4.0, 8.0)):
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
        zones=load_zones(str(zones_path)),
    )
    source = ReplayFrameSource(str(replay_path))

    labels: list[str] = []
    zone_event_types: list[str] = []
    final_zone_state = None
    while True:
        packet = source.read()
        if packet is None:
            break
        output = pipeline.process(packet)
        final_zone_state = output.zone_states[0]
        labels.append(final_zone_state.context.label.value)
        zone_event_types.extend(event.event_type for event in output.events if event.event_type.startswith("zone_"))
    source.close()

    assert labels == ["solo_focus", "solo_focus", "solo_focus"]
    assert zone_event_types == ["zone_occupied", "zone_focus_started"]
    assert final_zone_state is not None
    assert final_zone_state.temporal_state.current_label_duration_seconds == 8.0
