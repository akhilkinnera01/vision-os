"""Event metadata source coverage for the trigger engine."""

from __future__ import annotations

from common.models import ContextLabel, Decision, SceneMetrics, TemporalState, VisionEvent
from integrations import TriggerAction, TriggerCondition, TriggerConfig, TriggerEngine, TriggerRule
from integrations.models import TriggerSnapshot


def test_trigger_engine_supports_event_metadata_sources() -> None:
    engine = TriggerEngine(
        TriggerConfig(
            rules=(
                TriggerRule(
                    rule_id="whiteboard-group",
                    condition=TriggerCondition(
                        source="event.metadata.zone_id",
                        operator="equals",
                        value="whiteboard",
                    ),
                    actions=(TriggerAction(action_type="stdout"),),
                ),
            )
        )
    )

    records = engine.evaluate(
        TriggerSnapshot(
            timestamp=3.0,
            decision=Decision(
                label=ContextLabel.GROUP_ACTIVITY,
                confidence=0.84,
                action="support collaboration",
                scene_metrics=SceneMetrics(),
            ),
            temporal_state=TemporalState(),
            events=(
                VisionEvent(
                    event_type="zone_group_started",
                    timestamp=3.0,
                    description="Whiteboard entered group activity",
                    metadata={"zone_id": "whiteboard", "zone_label": "group_activity"},
                ),
            ),
            zone_states=(),
        )
    )

    assert len(records) == 1
    assert records[0].trigger_id == "whiteboard-group"
