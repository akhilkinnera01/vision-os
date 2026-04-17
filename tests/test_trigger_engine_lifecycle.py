"""Lifecycle tests for the stateful trigger engine."""

from __future__ import annotations

from common.models import ContextLabel, Decision, SceneMetrics, TemporalState
from integrations import TriggerAction, TriggerCondition, TriggerConfig, TriggerEngine, TriggerRule
from integrations.models import TriggerSnapshot


def _decision(label: ContextLabel = ContextLabel.FOCUSED_WORK) -> Decision:
    return Decision(
        label=label,
        confidence=0.92,
        action="stay focused",
        scene_metrics=SceneMetrics(),
    )


def _snapshot(timestamp: float, label: ContextLabel = ContextLabel.FOCUSED_WORK) -> TriggerSnapshot:
    return TriggerSnapshot(
        timestamp=timestamp,
        decision=_decision(label),
        temporal_state=TemporalState(),
        events=(),
        zone_states=(),
    )


def _label_rule(
    *,
    min_duration_seconds: float = 0.0,
    cooldown_seconds: float = 0.0,
    rearm_on_clear: bool = True,
) -> TriggerRule:
    return TriggerRule(
        rule_id="focus-session",
        condition=TriggerCondition(
            source="decision.label",
            operator="equals",
            value="Focused Work",
            min_duration_seconds=min_duration_seconds,
        ),
        actions=(TriggerAction(action_type="stdout"),),
        cooldown_seconds=cooldown_seconds,
        rearm_on_clear=rearm_on_clear,
    )


def test_trigger_engine_does_not_emit_before_min_duration_is_reached() -> None:
    engine = TriggerEngine(TriggerConfig(rules=(_label_rule(min_duration_seconds=5.0),)))

    first = engine.evaluate(_snapshot(0.0))
    second = engine.evaluate(_snapshot(4.9))

    assert first == ()
    assert second == ()


def test_trigger_engine_emits_once_when_min_duration_is_satisfied() -> None:
    engine = TriggerEngine(TriggerConfig(rules=(_label_rule(min_duration_seconds=5.0),)))

    engine.evaluate(_snapshot(0.0))
    emitted = engine.evaluate(_snapshot(5.0))
    duplicate = engine.evaluate(_snapshot(9.0))

    assert len(emitted) == 1
    assert emitted[0].trigger_id == "focus-session"
    assert duplicate == ()


def test_trigger_engine_enforces_cooldown_after_emission() -> None:
    engine = TriggerEngine(TriggerConfig(rules=(_label_rule(cooldown_seconds=10.0),)))

    first = engine.evaluate(_snapshot(0.0))
    engine.evaluate(_snapshot(1.0, label=ContextLabel.CASUAL_USE))
    blocked = engine.evaluate(_snapshot(5.0))
    allowed = engine.evaluate(_snapshot(12.0))

    assert len(first) == 1
    assert blocked == ()
    assert len(allowed) == 1


def test_trigger_engine_requires_clear_state_before_rearm() -> None:
    engine = TriggerEngine(TriggerConfig(rules=(_label_rule(),)))

    first = engine.evaluate(_snapshot(0.0))
    still_active = engine.evaluate(_snapshot(4.0))
    engine.evaluate(_snapshot(5.0, label=ContextLabel.CASUAL_USE))
    rearmed = engine.evaluate(_snapshot(6.0))

    assert len(first) == 1
    assert still_active == ()
    assert len(rearmed) == 1


def test_trigger_engine_event_rules_do_not_need_a_clear_state() -> None:
    from common.models import VisionEvent

    engine = TriggerEngine(
        TriggerConfig(
            rules=(
                TriggerRule(
                    rule_id="distraction-alert",
                    condition=TriggerCondition(
                        source="event.event_type",
                        operator="equals",
                        value="distraction_started",
                    ),
                    actions=(TriggerAction(action_type="stdout"),),
                    cooldown_seconds=5.0,
                ),
            )
        )
    )

    first = engine.evaluate(
        TriggerSnapshot(
            timestamp=0.0,
            decision=_decision(),
            temporal_state=TemporalState(),
            events=(VisionEvent(event_type="distraction_started", timestamp=0.0, description="x"),),
            zone_states=(),
        )
    )
    blocked = engine.evaluate(
        TriggerSnapshot(
            timestamp=3.0,
            decision=_decision(),
            temporal_state=TemporalState(),
            events=(VisionEvent(event_type="distraction_started", timestamp=3.0, description="x"),),
            zone_states=(),
        )
    )
    allowed = engine.evaluate(
        TriggerSnapshot(
            timestamp=6.0,
            decision=_decision(),
            temporal_state=TemporalState(),
            events=(VisionEvent(event_type="distraction_started", timestamp=6.0, description="x"),),
            zone_states=(),
        )
    )

    assert len(first) == 1
    assert blocked == ()
    assert len(allowed) == 1
