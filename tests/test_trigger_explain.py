"""Trigger-specific explanation coverage."""

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
from integrations import TriggeredActionRecord


def test_explanation_surfaces_recent_trigger_ids() -> None:
    explanation = ExplanationEngine().explain(
        Decision(
            label=ContextLabel.FOCUSED_WORK,
            confidence=0.91,
            action="stay focused",
            scene_metrics=SceneMetrics(focus_score=0.9, stability_score=0.95),
        ),
        SceneContext(
            label=ContextLabel.FOCUSED_WORK,
            confidence=0.91,
            signals=["laptop nearby"],
            confidence_reason="stable focus signals",
        ),
        SceneFeatures(),
        TemporalState(),
        RuntimeMetrics(frames_processed=3, fps=10.0, average_inference_ms=12.0),
        trigger_records=(
            TriggeredActionRecord(
                trigger_id="focus-session",
                action_type="file_append",
                timestamp=12.0,
                target="out/focus.jsonl",
                payload={"trigger_id": "focus-session"},
                success=True,
            ),
        ),
    )

    assert any("focus-session" in line for line in explanation.debug_lines)
