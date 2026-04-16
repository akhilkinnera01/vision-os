"""Replay-based regression tests with golden expectations."""

from __future__ import annotations

import json
from pathlib import Path

from common.config import VisionOSConfig
from common.models import OverlayMode, SourceMode
from common.policy import load_policy
from runtime.io import ReplayFrameSource
from runtime.pipeline import VisionPipeline


FIXTURE_DIR = Path(__file__).parent / "replays"
GOLDEN_DIR = Path(__file__).parent / "golden"


def evaluate_replay(name: str) -> dict[str, object]:
    source = ReplayFrameSource(str(FIXTURE_DIR / f"{name}.jsonl"))
    pipeline = VisionPipeline(
        VisionOSConfig(
            source_mode=SourceMode.REPLAY,
            input_path=str(FIXTURE_DIR / f"{name}.jsonl"),
            overlay_mode=OverlayMode.DEBUG,
            headless=True,
        ),
        policy=load_policy("default"),
    )

    labels: list[str] = []
    event_types: list[str] = []
    stability_scores: list[float] = []
    try:
        while True:
            packet = source.read()
            if packet is None:
                break
            output = pipeline.process(packet)
            labels.append(output.decision.label.value)
            event_types.extend(event.event_type for event in output.events)
            stability_scores.append(output.runtime_metrics.scene_stability_score)
    finally:
        source.close()

    return {
        "labels": labels,
        "event_types": event_types,
        "average_inference_ms": pipeline.benchmark_tracker.summary().average_inference_ms,
        "min_stability_score": min(stability_scores) if stability_scores else 0.0,
    }


def assert_matches_golden(name: str) -> None:
    expected = json.loads((GOLDEN_DIR / f"{name}.expected.json").read_text(encoding="utf-8"))
    actual = evaluate_replay(name)

    assert actual["labels"] == expected["labels"]
    assert actual["event_types"] == expected["event_types"]
    assert actual["average_inference_ms"] <= expected["max_average_inference_ms"]
    assert actual["min_stability_score"] >= expected["min_stability_score"]


def test_focused_work_replay_matches_golden() -> None:
    assert_matches_golden("focused_work")


def test_distraction_spike_replay_matches_golden() -> None:
    assert_matches_golden("distraction_spike")


def test_collaboration_growth_replay_matches_golden() -> None:
    assert_matches_golden("collaboration_growth")
