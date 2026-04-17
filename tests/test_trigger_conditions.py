"""Condition-source coverage for the trigger engine."""

from __future__ import annotations

from common.models import ContextLabel, Decision, SceneMetrics, TemporalState
from integrations import TriggerAction, TriggerCondition, TriggerConfig, TriggerEngine, TriggerRule
from integrations.models import TriggerSnapshot


def test_trigger_engine_supports_decision_confidence_thresholds() -> None:
    engine = TriggerEngine(
        TriggerConfig(
            rules=(
                TriggerRule(
                    rule_id="high-confidence-focus",
                    condition=TriggerCondition(
                        source="decision.confidence",
                        operator="gte",
                        value=0.9,
                    ),
                    actions=(TriggerAction(action_type="stdout"),),
                ),
            )
        )
    )

    records = engine.evaluate(
        TriggerSnapshot(
            timestamp=2.0,
            decision=Decision(
                label=ContextLabel.FOCUSED_WORK,
                confidence=0.93,
                action="stay focused",
                scene_metrics=SceneMetrics(),
            ),
            temporal_state=TemporalState(),
        )
    )

    assert len(records) == 1
    assert records[0].trigger_id == "high-confidence-focus"


def test_trigger_engine_supports_boolean_temporal_metrics() -> None:
    engine = TriggerEngine(
        TriggerConfig(
            rules=(
                TriggerRule(
                    rule_id="unstable-context",
                    condition=TriggerCondition(
                        source="temporal.metrics.context_unstable",
                        operator="equals",
                        value=True,
                    ),
                    actions=(TriggerAction(action_type="stdout"),),
                ),
            )
        )
    )

    records = engine.evaluate(
        TriggerSnapshot(
            timestamp=2.0,
            decision=Decision(
                label=ContextLabel.CASUAL_USE,
                confidence=0.61,
                action="hold steady",
                scene_metrics=SceneMetrics(),
            ),
            temporal_state=TemporalState(
                metrics=SceneMetrics(context_unstable=True),
            ),
        )
    )

    assert len(records) == 1
    assert records[0].trigger_id == "unstable-context"
