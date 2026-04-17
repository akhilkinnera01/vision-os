"""Load trigger rules and integration outputs from YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class IntegrationConfigError(ValueError):
    """Raised when a trigger/integration config is malformed."""


@dataclass(slots=True, frozen=True)
class TriggerRule:
    """One event-driven trigger rule."""

    rule_id: str
    event_type: str
    zone_id: str | None = None
    log_path: str | None = None
    webhook_url: str | None = None
    mqtt_host: str | None = None
    mqtt_port: int = 1883
    mqtt_topic: str | None = None


@dataclass(slots=True, frozen=True)
class TriggerConfig:
    """Loaded trigger rules for the runtime."""

    rules: tuple[TriggerRule, ...]


def load_trigger_config(path: str) -> TriggerConfig:
    """Load and validate the trigger YAML file."""
    config_path = Path(path)
    if not config_path.is_file():
        raise IntegrationConfigError(f"Trigger config not found: {config_path}")

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise IntegrationConfigError(f"Trigger config root must be a mapping: {config_path}")

    raw_rules = payload.get("triggers")
    if not isinstance(raw_rules, list) or not raw_rules:
        raise IntegrationConfigError("Trigger config must define a non-empty 'triggers' list.")

    rules: list[TriggerRule] = []
    seen_ids: set[str] = set()
    for index, raw_rule in enumerate(raw_rules):
        rule = _parse_rule(raw_rule, index)
        if rule.rule_id in seen_ids:
            raise IntegrationConfigError(f"Duplicate trigger rule id: {rule.rule_id}")
        seen_ids.add(rule.rule_id)
        rules.append(rule)
    return TriggerConfig(rules=tuple(rules))


def _parse_rule(payload: object, index: int) -> TriggerRule:
    if not isinstance(payload, dict):
        raise IntegrationConfigError(f"Trigger at index {index} must be a mapping.")

    rule_id = _require_string(payload, "id", index)
    event_type = _require_string(payload, "event_type", index)
    zone_id = _optional_string(payload, "zone_id", rule_id)
    log_path = _optional_string(payload, "log_path", rule_id)
    webhook_url = _optional_string(payload, "webhook_url", rule_id)
    mqtt_host = _optional_string(payload, "mqtt_host", rule_id)
    mqtt_topic = _optional_string(payload, "mqtt_topic", rule_id)

    mqtt_port = int(payload.get("mqtt_port", 1883))
    if mqtt_port <= 0:
        raise IntegrationConfigError(f"Trigger '{rule_id}' field 'mqtt_port' must be > 0.")

    if not any((log_path, webhook_url, mqtt_topic)):
        raise IntegrationConfigError(f"Trigger '{rule_id}' must define at least one output target.")
    if mqtt_topic and not mqtt_host:
        raise IntegrationConfigError(f"Trigger '{rule_id}' requires 'mqtt_host' when 'mqtt_topic' is set.")

    return TriggerRule(
        rule_id=rule_id,
        event_type=event_type,
        zone_id=zone_id,
        log_path=log_path,
        webhook_url=webhook_url,
        mqtt_host=mqtt_host,
        mqtt_port=mqtt_port,
        mqtt_topic=mqtt_topic,
    )


def _require_string(payload: dict[str, object], key: str, index: int) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise IntegrationConfigError(f"Trigger at index {index} must define a non-empty '{key}' field.")
    return value.strip()


def _optional_string(payload: dict[str, object], key: str, rule_id: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise IntegrationConfigError(f"Trigger '{rule_id}' field '{key}' must be a non-empty string when present.")
    return value.strip()
