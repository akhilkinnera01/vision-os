"""Typed trigger and generic integration models."""

from __future__ import annotations

from dataclasses import dataclass, field

from common.models import Decision, TemporalState, VisionEvent
from zones.models import ZoneRuntimeState


@dataclass(slots=True, frozen=True)
class IntegrationTarget:
    """One configured delivery target for a runtime integration source."""

    integration_id: str
    target_type: str
    source: str
    enabled: bool = True
    target: str | None = None
    method: str = "POST"
    mqtt_host: str | None = None
    mqtt_port: int = 1883
    mqtt_topic: str | None = None
    event_types: tuple[str, ...] = ()
    trigger_ids: tuple[str, ...] = ()
    interval_seconds: float | None = None


@dataclass(slots=True, frozen=True)
class IntegrationConfig:
    """Loaded generic integration targets for the runtime."""

    targets: tuple[IntegrationTarget, ...]


@dataclass(slots=True, frozen=True)
class IntegrationEnvelope:
    """One structured outbound message emitted by the generic integration layer."""

    source: str
    timestamp: float
    source_mode: str
    scene_label: str | None
    confidence: float | None
    profile_id: str | None = None
    metrics: dict[str, object] = field(default_factory=dict)
    risk_flags: tuple[str, ...] = ()
    payload: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "timestamp": self.timestamp,
            "source_mode": self.source_mode,
            "scene_label": self.scene_label,
            "confidence": self.confidence,
            "profile_id": self.profile_id,
            "metrics": self.metrics,
            "risk_flags": list(self.risk_flags),
            "payload": self.payload,
        }


@dataclass(slots=True, frozen=True)
class DispatchRecord:
    """One attempted generic integration dispatch."""

    integration_id: str
    target_type: str
    source: str
    timestamp: float
    target: str | None
    payload: dict[str, object]
    success: bool
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "integration_id": self.integration_id,
            "target_type": self.target_type,
            "source": self.source,
            "timestamp": self.timestamp,
            "target": self.target,
            "payload": self.payload,
            "success": self.success,
            "error": self.error,
        }


@dataclass(slots=True, frozen=True)
class TriggerCondition:
    """One declarative condition checked against runtime state."""

    source: str
    operator: str
    value: object
    min_duration_seconds: float = 0.0
    event_metadata_filters: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class TriggerAction:
    """One sink action executed when a trigger fires."""

    action_type: str
    target: str | None = None
    method: str = "POST"
    mqtt_host: str | None = None
    mqtt_port: int = 1883
    mqtt_topic: str | None = None


@dataclass(slots=True, frozen=True)
class TriggerRule:
    """One trigger rule with canonical fields plus legacy compatibility fields."""

    rule_id: str
    condition: TriggerCondition | None = None
    actions: tuple[TriggerAction, ...] = ()
    enabled: bool = True
    cooldown_seconds: float = 0.0
    repeat_interval_seconds: float | None = None
    rearm_on_clear: bool = True
    event_type: str | None = None
    zone_id: str | None = None
    log_path: str | None = None
    webhook_url: str | None = None
    mqtt_host: str | None = None
    mqtt_port: int = 1883
    mqtt_topic: str | None = None

    def __post_init__(self) -> None:
        condition = self.condition
        actions = self.actions

        if condition is None and self.event_type is not None:
            condition = TriggerCondition(
                source="event.event_type",
                operator="equals",
                value=self.event_type,
                event_metadata_filters={"zone_id": self.zone_id} if self.zone_id is not None else {},
            )
        if not actions:
            legacy_actions: list[TriggerAction] = []
            if self.log_path:
                legacy_actions.append(TriggerAction(action_type="file_append", target=self.log_path))
            if self.webhook_url:
                legacy_actions.append(
                    TriggerAction(action_type="webhook", target=self.webhook_url, method="POST")
                )
            if self.mqtt_host and self.mqtt_topic:
                legacy_actions.append(
                    TriggerAction(
                        action_type="mqtt_publish",
                        target=self.mqtt_topic,
                        mqtt_host=self.mqtt_host,
                        mqtt_port=self.mqtt_port,
                        mqtt_topic=self.mqtt_topic,
                    )
                )
            actions = tuple(legacy_actions)

        object.__setattr__(self, "condition", condition)
        object.__setattr__(self, "actions", tuple(actions))


@dataclass(slots=True, frozen=True)
class TriggerConfig:
    """Loaded trigger rules for the runtime."""

    rules: tuple[TriggerRule, ...]


@dataclass(slots=True, frozen=True)
class TriggerSnapshot:
    """Frame-scoped runtime state evaluated by the trigger engine."""

    timestamp: float
    decision: Decision
    temporal_state: TemporalState
    events: tuple[VisionEvent, ...] = ()
    zone_states: tuple[ZoneRuntimeState, ...] = ()


@dataclass(slots=True)
class TriggerRuleState:
    """Per-rule lifecycle state retained across packets."""

    armed: bool = True
    condition_was_true: bool = False
    fired_in_current_streak: bool = False
    satisfied_since: float | None = None
    last_fired_at: float | None = None
    fire_count: int = 0


@dataclass(slots=True, frozen=True)
class TriggeredActionRecord:
    """One attempted action emitted by the trigger engine."""

    trigger_id: str
    action_type: str
    timestamp: float
    target: str | None
    payload: dict[str, object]
    success: bool
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "trigger_id": self.trigger_id,
            "action_type": self.action_type,
            "timestamp": self.timestamp,
            "target": self.target,
            "payload": self.payload,
            "success": self.success,
            "error": self.error,
        }
