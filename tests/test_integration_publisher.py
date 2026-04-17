"""Tests for the runtime integration publisher."""

from __future__ import annotations

from common.models import ContextLabel, Decision, HistoryRecord, RuntimeMetrics, SceneMetrics, SessionAnalyticsSummary, VisionEvent
from integrations import DispatchRecord, IntegrationConfig, IntegrationTarget, TriggeredActionRecord
from integrations.publisher import IntegrationPublisher


class _RecordingDispatcher:
    def __init__(self) -> None:
        self.calls: list[tuple[tuple[IntegrationTarget, ...], object]] = []

    def dispatch_many(self, targets, envelope):
        self.calls.append((targets, envelope))
        return tuple(
            DispatchRecord(
                integration_id=target.integration_id,
                target_type=target.target_type,
                source=envelope.source,
                timestamp=envelope.timestamp,
                target=target.target,
                payload=envelope.to_dict(),
                success=True,
            )
            for target in targets
        )


def test_publisher_dispatches_event_and_deduped_trigger_envelopes() -> None:
    dispatcher = _RecordingDispatcher()
    publisher = IntegrationPublisher(
        IntegrationConfig(
            targets=(
                IntegrationTarget(
                    integration_id="event-log",
                    target_type="file_append",
                    source="event",
                    target="out/events.jsonl",
                    event_types=("distraction_started",),
                ),
                IntegrationTarget(
                    integration_id="trigger-hook",
                    target_type="webhook",
                    source="trigger",
                    target="https://example.invalid/trigger",
                    trigger_ids=("focus-session",),
                ),
            )
        ),
        dispatcher=dispatcher,
        source_mode="video",
        profile_id="meeting_room",
    )

    records = publisher.publish_runtime(
        decision=_decision(),
        runtime_metrics=_runtime_metrics(),
        history_record=_history_record(timestamp=12.0),
        events=(
            VisionEvent(
                event_type="distraction_started",
                timestamp=12.0,
                description="Phone engagement spiked",
                scene_label="Focused Work",
            ),
            VisionEvent(
                event_type="focus_resumed",
                timestamp=12.1,
                description="Focus resumed",
                scene_label="Focused Work",
            ),
        ),
        trigger_records=(
            TriggeredActionRecord(
                trigger_id="focus-session",
                action_type="stdout",
                timestamp=12.0,
                target=None,
                payload={"trigger_id": "focus-session", "label": "Focused Work"},
                success=True,
            ),
            TriggeredActionRecord(
                trigger_id="focus-session",
                action_type="file_append",
                timestamp=12.0,
                target="out/trigger.jsonl",
                payload={"trigger_id": "focus-session", "label": "Focused Work"},
                success=True,
            ),
        ),
    )

    assert len(records) == 2
    assert len(dispatcher.calls) == 2
    event_targets, event_envelope = dispatcher.calls[0]
    trigger_targets, trigger_envelope = dispatcher.calls[1]

    assert event_targets[0].integration_id == "event-log"
    assert event_envelope.source == "event"
    assert event_envelope.payload["event_type"] == "distraction_started"
    assert trigger_targets[0].integration_id == "trigger-hook"
    assert trigger_envelope.source == "trigger"
    assert trigger_envelope.payload["trigger_id"] == "focus-session"
    assert trigger_envelope.payload["action_types"] == ["stdout", "file_append"]


def test_publisher_rate_limits_status_targets() -> None:
    dispatcher = _RecordingDispatcher()
    publisher = IntegrationPublisher(
        IntegrationConfig(
            targets=(
                IntegrationTarget(
                    integration_id="status-log",
                    target_type="file_append",
                    source="status",
                    target="out/status.jsonl",
                    interval_seconds=5.0,
                ),
            )
        ),
        dispatcher=dispatcher,
        source_mode="replay",
        profile_id="workstation",
    )

    first = publisher.publish_runtime(
        decision=_decision(),
        runtime_metrics=_runtime_metrics(),
        history_record=_history_record(timestamp=2.0),
        events=(),
        trigger_records=(),
    )
    second = publisher.publish_runtime(
        decision=_decision(),
        runtime_metrics=_runtime_metrics(),
        history_record=_history_record(timestamp=4.0),
        events=(),
        trigger_records=(),
    )
    third = publisher.publish_runtime(
        decision=_decision(),
        runtime_metrics=_runtime_metrics(),
        history_record=_history_record(timestamp=8.5),
        events=(),
        trigger_records=(),
    )

    assert len(first) == 1
    assert second == ()
    assert len(third) == 1
    assert len(dispatcher.calls) == 2
    assert dispatcher.calls[0][1].source == "status"
    assert dispatcher.calls[1][1].timestamp == 8.5


def test_publisher_dispatches_session_summary_targets() -> None:
    dispatcher = _RecordingDispatcher()
    publisher = IntegrationPublisher(
        IntegrationConfig(
            targets=(
                IntegrationTarget(
                    integration_id="summary-mqtt",
                    target_type="mqtt_publish",
                    source="session_summary",
                    target="visionos/summary",
                    mqtt_host="127.0.0.1",
                    mqtt_port=1883,
                    mqtt_topic="visionos/summary",
                ),
            )
        ),
        dispatcher=dispatcher,
        source_mode="video",
        profile_id="study_room",
    )

    records = publisher.publish_session_summary(
        SessionAnalyticsSummary(
            started_at=1.0,
            ended_at=20.0,
            duration_seconds=19.0,
            frames_processed=40,
            dominant_scene_label="Focused Work",
        )
    )

    assert len(records) == 1
    assert len(dispatcher.calls) == 1
    _, envelope = dispatcher.calls[0]
    assert envelope.source == "session_summary"
    assert envelope.payload["dominant_scene_label"] == "Focused Work"


def _decision() -> Decision:
    return Decision(
        label=ContextLabel.FOCUSED_WORK,
        confidence=0.91,
        action="protect_focus",
        reasoning_facts=["Laptop and monitor are both centered"],
        risk_flags=["phone_nearby"],
        scene_metrics=SceneMetrics(
            focus_score=0.92,
            distraction_score=0.17,
            collaboration_score=0.08,
            stability_score=0.88,
            focus_duration_seconds=12.0,
            decision_switch_rate=0.1,
        ),
    )


def _runtime_metrics() -> RuntimeMetrics:
    return RuntimeMetrics(
        frames_processed=10,
        fps=15.0,
        average_inference_ms=23.4,
        dropped_frames=0,
        scene_stability_score=0.88,
        stage_timings={"decision": 1.2},
    )


def _history_record(*, timestamp: float) -> HistoryRecord:
    return HistoryRecord(
        frame_index=4,
        timestamp=timestamp,
        scene_label="Focused Work",
        confidence=0.91,
        action="protect_focus",
        risk_flags=("phone_nearby",),
        focus_score=0.92,
        distraction_score=0.17,
        collaboration_score=0.08,
        stability_score=0.88,
        focus_duration_seconds=12.0,
        decision_switch_rate=0.1,
        average_inference_ms=23.4,
        fps=15.0,
        dropped_frames=0,
        event_types=("distraction_started",),
        trigger_ids=("focus-session",),
        zone_labels={"desk_a": "Focused Work"},
        stage_timings={"decision": 1.2},
    )
