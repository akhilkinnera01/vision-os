"""Payload schema checks for fired trigger records."""

from __future__ import annotations

from common.models import ContextLabel, Decision, SceneMetrics, TemporalState
from integrations import TriggerAction, TriggerCondition, TriggerConfig, TriggerEngine, TriggerRule
from integrations.models import TriggerSnapshot


def test_trigger_payload_serialization_matches_expected_schema() -> None:
    engine = TriggerEngine(
        TriggerConfig(
            rules=(
                TriggerRule(
                    rule_id="focus-session",
                    condition=TriggerCondition(
                        source="decision.label",
                        operator="equals",
                        value="Focused Work",
                    ),
                    actions=(TriggerAction(action_type="stdout"),),
                ),
            )
        )
    )

    records = engine.evaluate(
        TriggerSnapshot(
            timestamp=12.0,
            decision=Decision(
                label=ContextLabel.FOCUSED_WORK,
                confidence=0.93,
                action="stay focused",
                scene_metrics=SceneMetrics(
                    focus_score=0.88,
                    distraction_score=0.12,
                    collaboration_score=0.18,
                    stability_score=0.95,
                ),
            ),
            temporal_state=TemporalState(),
            events=(),
            zone_states=(),
        )
    )

    assert len(records) == 1
    payload = records[0].payload
    assert payload["trigger_id"] == "focus-session"
    assert payload["timestamp"] == 12.0
    assert payload["label"] == "Focused Work"
    assert payload["confidence"] == 0.93
    assert payload["metrics"] == {
        "focus": 0.88,
        "distraction": 0.12,
        "collaboration": 0.18,
        "stability": 0.95,
    }
    assert payload["event"] is None
