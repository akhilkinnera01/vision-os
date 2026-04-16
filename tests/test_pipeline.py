"""Unit tests for the reasoning pipeline that avoid webcam dependencies."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app import _validate_input_path
from common.config import VisionOSConfig
from common.models import (
    BoundingBox,
    ContextLabel,
    Detection,
    ReplayRecord,
    RuntimeMetrics,
    SceneMetrics,
    SourceMode,
    TemporalState,
    VisionEvent,
)
from context.rules import ContextRulesEngine
from decision.engine import DecisionEngine
from explain.explain import ExplanationEngine
from features.builder import FeatureBuilder
from runtime.benchmark import BenchmarkTracker
from runtime.io import ReplayFrameSource, ReplayRecorder
from state.memory import TemporalMemory


def make_detection(
    label: str,
    bbox: tuple[int, int, int, int] = (0, 0, 100, 100),
    confidence: float = 0.9,
) -> Detection:
    """Create a synthetic detection for deterministic scenarios."""
    box = BoundingBox(*bbox)
    return Detection(
        label=label,
        confidence=confidence,
        bbox=box,
        area_ratio=(box.area / float(1280 * 720)) if box.area else 0.0,
    )


def test_spatial_features_detect_proximity_and_centering() -> None:
    builder = FeatureBuilder()
    features = builder.build(
        [
            make_detection("person", (200, 200, 360, 520)),
            make_detection("laptop", (330, 360, 530, 520)),
            make_detection("cell phone", (320, 280, 360, 340)),
            make_detection("monitor", (420, 120, 860, 420)),
        ],
        (720, 1280),
    )

    assert features.laptop_near_person is True
    assert features.phone_near_person is True
    assert features.centered_monitor is True
    assert features.desk_like_score > 0.3


def test_group_activity_uses_clustered_people() -> None:
    builder = FeatureBuilder()
    rules = ContextRulesEngine()

    features = builder.build(
        [
            make_detection("person", (300, 120, 430, 520)),
            make_detection("person", (430, 130, 560, 520)),
            make_detection("chair", (350, 420, 460, 650)),
        ],
        (720, 1280),
    )
    scene_context = rules.infer(features)

    assert features.multiple_people_clustered is True
    assert scene_context.label == ContextLabel.GROUP_ACTIVITY


def test_temporal_memory_tracks_sustained_focus() -> None:
    builder = FeatureBuilder()
    memory = TemporalMemory(window_seconds=10.0)

    features = builder.build(
        [
            make_detection("person", (250, 140, 420, 600)),
            make_detection("laptop", (370, 360, 620, 560)),
            make_detection("keyboard", (340, 520, 640, 640)),
        ],
        (720, 1280),
    )
    memory.update(0.0, features, ContextLabel.FOCUSED_WORK, 0.8)
    memory.update(4.0, features, ContextLabel.FOCUSED_WORK, 0.84)
    temporal_state = memory.update(8.0, features, ContextLabel.FOCUSED_WORK, 0.87)

    assert temporal_state.metrics.focus_score > 0.6
    assert temporal_state.metrics.focus_duration_seconds == 8.0
    assert any("Focused Work for 8.0s" == note for note in temporal_state.notes)


def test_temporal_memory_detects_distraction_spike() -> None:
    builder = FeatureBuilder()
    memory = TemporalMemory(window_seconds=6.0)

    focused = builder.build(
        [make_detection("person"), make_detection("laptop"), make_detection("keyboard")],
        (720, 1280),
    )
    distracted = builder.build(
        [make_detection("person"), make_detection("cell phone"), make_detection("remote")],
        (720, 1280),
    )

    memory.update(0.0, focused, ContextLabel.FOCUSED_WORK, 0.82)
    memory.update(2.0, focused, ContextLabel.FOCUSED_WORK, 0.8)
    temporal_state = memory.update(4.0, distracted, ContextLabel.CASUAL_USE, 0.75)

    assert temporal_state.metrics.distraction_spike is True
    assert "Phone distraction spike" in temporal_state.notes


def test_decision_holds_when_context_is_unstable() -> None:
    decision_engine = DecisionEngine()
    scene_context = ContextRulesEngine().infer(
        FeatureBuilder().build([make_detection("cell phone"), make_detection("remote")], (720, 1280))
    )
    unstable_state = TemporalState(
        notes=["Context unstable"],
        metrics=SceneMetrics(context_unstable=True),
    )

    first_decision = decision_engine.decide(
        ContextRulesEngine().infer(
            FeatureBuilder().build([make_detection("person"), make_detection("laptop")], (720, 1280))
        ),
        FeatureBuilder().build([make_detection("person"), make_detection("laptop")], (720, 1280)),
        TemporalState(metrics=SceneMetrics()),
    )
    second_decision = decision_engine.decide(
        scene_context,
        FeatureBuilder().build([make_detection("cell phone"), make_detection("remote")], (720, 1280)),
        unstable_state,
    )

    assert first_decision.label == ContextLabel.FOCUSED_WORK
    assert second_decision.label == ContextLabel.FOCUSED_WORK
    assert second_decision.action == "Hold current label until context stabilizes"


def test_explanation_is_structured() -> None:
    builder = FeatureBuilder()
    rules = ContextRulesEngine()
    decision_engine = DecisionEngine()
    explanation_engine = ExplanationEngine()
    memory = TemporalMemory(window_seconds=8.0)

    features = builder.build(
        [make_detection("person"), make_detection("laptop"), make_detection("book")],
        (720, 1280),
    )
    provisional = rules.infer(features)
    temporal_state = memory.update(0.0, features, provisional.label, provisional.confidence)
    scene_context = rules.infer(features, temporal_state)
    decision = decision_engine.decide(scene_context, features, temporal_state)
    explanation = explanation_engine.explain(
        decision,
        scene_context,
        features,
        temporal_state,
        RuntimeMetrics(frames_processed=1, fps=0.0, average_inference_ms=12.5, dropped_frames=0),
    )

    assert explanation.scene_label == "Focused Work"
    assert explanation.action == decision.action
    assert "focus" in explanation.scores
    assert explanation.top_signals
    assert explanation.debug_lines


def test_replay_record_round_trip(tmp_path: Path) -> None:
    output_path = tmp_path / "session.jsonl"
    recorder = ReplayRecorder(str(output_path), source_mode=SourceMode.WEBCAM)
    detections = [make_detection("person", (100, 100, 250, 400)), make_detection("laptop", (260, 280, 480, 420))]
    recorder.write(
        frame_index=3,
        timestamp=1.25,
        frame_shape=(720, 1280),
        detections=detections,
        events=[
            VisionEvent(
                event_type="focus_sustained",
                timestamp=1.25,
                description="Focused work held",
                scene_label="Focused Work",
            )
        ],
    )
    recorder.close()

    source = ReplayFrameSource(str(output_path))
    packet = source.read()
    source.close()

    assert packet is not None
    assert packet.frame_index == 3
    assert packet.replay_detections is not None
    assert packet.replay_detections[0].label == "person"
    assert packet.replay_events is not None
    assert packet.replay_events[0].event_type == "focus_sustained"
    assert packet.frame.shape == (720, 1280, 3)


def test_replay_recorder_creates_parent_directories(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "captures" / "session.jsonl"
    recorder = ReplayRecorder(str(output_path), source_mode=SourceMode.WEBCAM)
    recorder.write(frame_index=1, timestamp=0.5, frame_shape=(720, 1280), detections=[make_detection("person")])
    recorder.close()

    assert output_path.is_file()


def test_benchmark_tracker_summary() -> None:
    tracker = BenchmarkTracker()
    tracker.record_inference(0.0, 12.0, ContextLabel.FOCUSED_WORK)
    tracker.note_dropped_frame()
    tracker.record_inference(1.0, 18.0, ContextLabel.CASUAL_USE)
    summary = tracker.summary()

    assert summary.frames_processed == 2
    assert summary.dropped_frames == 1
    assert summary.average_inference_ms == 15.0
    assert summary.decision_switch_rate == 1.0


def test_benchmark_summary_creates_parent_directories(tmp_path: Path) -> None:
    tracker = BenchmarkTracker()
    tracker.record_inference(0.0, 9.0, ContextLabel.FOCUSED_WORK)
    output_path = tmp_path / "benchmarks" / "run" / "summary.json"
    tracker.write_summary(str(output_path))

    assert output_path.is_file()


def test_replay_record_serialization_is_stable() -> None:
    record = ReplayRecord(
        frame_index=2,
        timestamp=4.5,
        frame_shape=(720, 1280),
        detections=[make_detection("person", (10, 20, 30, 60))],
        source_mode=SourceMode.VIDEO,
    )

    payload = record.to_dict()
    restored = ReplayRecord.from_dict(payload)

    assert restored.frame_index == 2
    assert restored.source_mode.value == "video"
    assert restored.detections[0].bbox.x1 == 10


def test_renderer_safe_shape_fixture() -> None:
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    assert frame.shape == (720, 1280, 3)


def test_validate_input_path_rejects_missing_demo_input(tmp_path: Path) -> None:
    config = VisionOSConfig(source_mode=SourceMode.VIDEO, input_path=str(tmp_path / "missing.mp4"))

    with pytest.raises(FileNotFoundError, match="Video input not found"):
        _validate_input_path(config)
