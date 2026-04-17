"""Typed trigger and integration models."""

from __future__ import annotations

from dataclasses import dataclass, field


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
