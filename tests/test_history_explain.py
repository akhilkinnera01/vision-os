"""History-specific explanation coverage."""

from __future__ import annotations

from common.models import (
    ContextLabel,
    Decision,
    RuntimeMetrics,
    SceneContext,
    SceneFeatures,
    SceneMetrics,
    TemporalState,
)
from explain.explain import ExplanationEngine


def test_explanation_surfaces_temporal_history_summary() -> None:
    explanation = ExplanationEngine().explain(
        Decision(
            label=ContextLabel.FOCUSED_WORK,
            confidence=0.9,
            action="stay focused",
            scene_metrics=SceneMetrics(focus_score=0.88, focus_duration_seconds=12.0, stability_score=0.93),
        ),
        SceneContext(
            label=ContextLabel.FOCUSED_WORK,
            confidence=0.9,
            signals=["person near laptop"],
            confidence_reason="stable focus cues",
        ),
        SceneFeatures(),
        TemporalState(
            window_span_seconds=8.0,
            dominant_label=ContextLabel.FOCUSED_WORK,
            label_switch_count=2,
        ),
        RuntimeMetrics(frames_processed=8, fps=12.5, average_inference_ms=15.0),
    )

    assert any("History:" in line for line in explanation.debug_lines)
    assert any("focus_duration=12.0s" in line for line in explanation.debug_lines)
    assert any("switches=2" in line for line in explanation.debug_lines)
