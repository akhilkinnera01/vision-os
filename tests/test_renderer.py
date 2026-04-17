"""Regression tests for renderer text layout and top-of-frame label placement."""

from __future__ import annotations

from common.models import (
    BoundingBox,
    ContextLabel,
    Decision,
    Explanation,
    RuntimeMetrics,
    SceneMetrics,
)
from ui.renderer import FrameRenderer
from zones import (
    ZoneContext,
    ZoneContextLabel,
    ZoneDecision,
    ZoneFeatureSet,
    ZonePoint,
    ZoneRuntimeState,
    ZoneTemporalState,
    ZoneType,
)


def make_decision() -> Decision:
    """Create a stable decision payload for renderer-focused tests."""
    return Decision(
        label=ContextLabel.CASUAL_USE,
        confidence=0.62,
        action="Stay in passive observation mode",
        scene_metrics=SceneMetrics(
            focus_score=0.2,
            distraction_score=0.32,
            collaboration_score=0.13,
            stability_score=0.89,
        ),
    )


def make_explanation() -> Explanation:
    """Create a text-heavy explanation that forces wrapping in the header."""
    return Explanation(
        scene_label="Casual Use",
        top_signals=[
            "scene cues are limited",
            "desk occupancy is low",
            "focused workstation objects are missing",
        ],
        risk_flags=["context unstable"],
        action="Stay in passive observation mode",
        confidence_reason="Current cues are mixed and low-confidence.",
        compact_summary=(
            "Why: scene cues are limited, desk occupancy is low, and focused workstation "
            "objects are missing from the current frame."
        ),
        debug_lines=[
            "Top signals: scene cues are limited, desk occupancy is low, focused workstation objects are missing",
            "Action: Stay in passive observation mode",
            "Confidence reason: Current cues are mixed and low-confidence.",
            "Temporal notes: Context unstable, no sustained focus streak",
        ],
        scores={
            "focus": 0.2,
            "distraction": 0.32,
            "collaboration": 0.13,
            "stability": 0.89,
        },
        recent_events=["stability_warning"],
        zone_summaries=["Desk A=solo_focus", "Desk B=empty"],
    )


def make_zone_state() -> ZoneRuntimeState:
    return ZoneRuntimeState(
        zone_id="desk_a",
        zone_name="Desk A",
        zone_type=ZoneType.OCCUPANCY,
        feature_set=ZoneFeatureSet(
            zone_id="desk_a",
            zone_name="Desk A",
            zone_type=ZoneType.OCCUPANCY,
            occupied=True,
        ),
        context=ZoneContext(label=ZoneContextLabel.SOLO_FOCUS, confidence=0.88),
        decision=ZoneDecision(
            label=ZoneContextLabel.SOLO_FOCUS,
            confidence=0.88,
            action="Preserve focus-friendly zone state",
        ),
        temporal_state=ZoneTemporalState(stability_score=0.9),
        polygon=(
            ZonePoint(40.0, 220.0),
            ZonePoint(260.0, 220.0),
            ZonePoint(260.0, 460.0),
            ZonePoint(40.0, 460.0),
        ),
    )


def test_compact_header_layout_expands_and_stacks_wrapped_lines() -> None:
    renderer = FrameRenderer()
    layout = renderer._build_header_layout(
        frame_width=1280,
        frame_height=720,
        decision=make_decision(),
        explanation=make_explanation(),
        runtime_metrics=RuntimeMetrics(frames_processed=42, fps=11.3, average_inference_ms=28.4, dropped_frames=1),
    )

    assert layout.panel_height > 130
    assert layout.rows
    for previous, current in zip(layout.rows, layout.rows[1:]):
        assert current.top >= previous.bottom + renderer.LINE_GAP
    assert layout.rows[-1].bottom <= layout.panel_height - renderer.PANEL_PADDING_Y


def test_detection_label_anchor_stays_below_header_when_box_is_near_top() -> None:
    renderer = FrameRenderer()
    baseline_y = renderer._compute_detection_label_baseline(
        bbox=BoundingBox(12, 142, 100, 400),
        label_text="tv#53 0.70",
        header_bottom=176,
    )

    assert baseline_y > 176


def test_header_layout_includes_zone_summaries_without_overlap() -> None:
    renderer = FrameRenderer()
    layout = renderer._build_header_layout(
        frame_width=1280,
        frame_height=720,
        decision=make_decision(),
        explanation=make_explanation(),
        runtime_metrics=RuntimeMetrics(frames_processed=42, fps=11.3, average_inference_ms=28.4, dropped_frames=1),
    )

    assert any("Zones:" in row.text for row in layout.rows)
    for previous, current in zip(layout.rows, layout.rows[1:]):
        assert current.top >= previous.bottom + renderer.LINE_GAP


def test_renderer_accepts_zone_states_for_overlay() -> None:
    import numpy as np

    renderer = FrameRenderer()
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    annotated = renderer.render(
        frame,
        detections=[],
        decision=make_decision(),
        explanation=make_explanation(),
        runtime_metrics=RuntimeMetrics(frames_processed=1, fps=0.0, average_inference_ms=12.5, dropped_frames=0),
        zone_states=(make_zone_state(),),
    )

    assert annotated.shape == frame.shape
