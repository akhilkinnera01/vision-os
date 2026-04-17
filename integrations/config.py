"""Load trigger rules and generic integration targets from YAML."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from urllib.parse import urlparse

import yaml

from common.models import SceneMetrics
from integrations.models import IntegrationConfig, IntegrationTarget, TriggerAction, TriggerCondition, TriggerConfig, TriggerRule


class IntegrationConfigError(ValueError):
    """Raised when a trigger/integration config is malformed."""


SUPPORTED_INTEGRATION_SOURCES = frozenset({"event", "session_summary", "status", "trigger"})
SUPPORTED_INTEGRATION_TARGET_TYPES = frozenset({"file_append", "log", "mqtt_publish", "stdout", "webhook"})
SUPPORTED_TRIGGER_OPERATORS = frozenset({"equals", "not_equals", "gte", "gt", "lte", "lt"})
SUPPORTED_TRIGGER_DECISION_SOURCES = frozenset({"decision.label", "decision.confidence"})
SUPPORTED_TEMPORAL_METRICS = frozenset(field.name for field in fields(SceneMetrics))
SUPPORTED_WEBHOOK_METHODS = frozenset({"DELETE", "PATCH", "POST", "PUT"})


def load_integration_config(path: str) -> IntegrationConfig:
    """Load and validate the generic integrations YAML file."""
    config_path = Path(path)
    if not config_path.is_file():
        raise IntegrationConfigError(f"Integration config not found: {config_path}")

    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise IntegrationConfigError(f"Integration config root must be a mapping: {config_path}")

    raw_targets = payload.get("integrations", [])
    if not isinstance(raw_targets, list):
        raise IntegrationConfigError("Integration config field 'integrations' must be a list.")

    targets: list[IntegrationTarget] = []
    seen_ids: set[str] = set()
    for index, raw_target in enumerate(raw_targets):
        target = _parse_integration_target(raw_target, index)
        if target.integration_id in seen_ids:
            raise IntegrationConfigError(f"Duplicate integration id: {target.integration_id}")
        seen_ids.add(target.integration_id)
        targets.append(target)
    return IntegrationConfig(targets=tuple(targets))


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
    enabled = _optional_bool(payload, "enabled", rule_id, default=True)
    cooldown_seconds = _numeric_field(payload, "cooldown_seconds", rule_id, default=0.0)
    if cooldown_seconds < 0:
        raise IntegrationConfigError(f"Trigger '{rule_id}' field 'cooldown_seconds' must be >= 0.")
    repeat_interval_seconds = _optional_numeric_field(payload, "repeat_interval_seconds", rule_id)
    if repeat_interval_seconds is not None and repeat_interval_seconds < 0:
        raise IntegrationConfigError(f"Trigger '{rule_id}' field 'repeat_interval_seconds' must be >= 0.")
    rearm_on_clear = _optional_bool(payload, "rearm_on_clear", rule_id, default=True)

    if "when" in payload:
        condition = _parse_condition(payload["when"], rule_id)
        actions = _parse_actions(payload.get("then"), rule_id)
        return TriggerRule(
            rule_id=rule_id,
            enabled=enabled,
            condition=condition,
            actions=actions,
            cooldown_seconds=cooldown_seconds,
            repeat_interval_seconds=repeat_interval_seconds,
            rearm_on_clear=rearm_on_clear,
        )

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
        enabled=enabled,
        cooldown_seconds=cooldown_seconds,
        repeat_interval_seconds=repeat_interval_seconds,
        rearm_on_clear=rearm_on_clear,
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


def _optional_bool(payload: dict[str, object], key: str, rule_id: str, default: bool) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise IntegrationConfigError(f"Trigger '{rule_id}' field '{key}' must be a boolean.")
    return value


def _numeric_field(payload: dict[str, object], key: str, rule_id: str, default: float = 0.0) -> float:
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IntegrationConfigError(f"Trigger '{rule_id}' field '{key}' must be numeric.")
    return float(value)


def _optional_numeric_field(payload: dict[str, object], key: str, rule_id: str) -> float | None:
    if key not in payload:
        return None
    return _numeric_field(payload, key, rule_id)


def _parse_condition(payload: object, rule_id: str) -> TriggerCondition:
    if not isinstance(payload, dict):
        raise IntegrationConfigError(f"Trigger '{rule_id}' field 'when' must be a mapping.")

    source = _require_string(payload, "source", 0)
    operator = _require_string(payload, "operator", 0)
    _validate_condition_source(rule_id, source)
    _validate_condition_operator(rule_id, operator)
    if "value" not in payload:
        raise IntegrationConfigError(f"Trigger '{rule_id}' field 'when.value' is required.")
    value = payload["value"]
    min_duration_seconds = _numeric_field(payload, "min_duration_seconds", rule_id, default=0.0)
    if min_duration_seconds < 0:
        raise IntegrationConfigError(f"Trigger '{rule_id}' field 'min_duration_seconds' must be >= 0.")
    if source.startswith("event.") and min_duration_seconds > 0:
        raise IntegrationConfigError(
            f"Trigger '{rule_id}' event-backed rules do not support min_duration_seconds."
        )

    event_metadata_filters = payload.get("event_metadata_filters", {})
    if event_metadata_filters is None:
        event_metadata_filters = {}
    if not isinstance(event_metadata_filters, dict):
        raise IntegrationConfigError(
            f"Trigger '{rule_id}' field 'when.event_metadata_filters' must be a mapping."
        )

    return TriggerCondition(
        source=source,
        operator=operator,
        value=value,
        min_duration_seconds=min_duration_seconds,
        event_metadata_filters=dict(event_metadata_filters),
    )


def _parse_actions(payload: object, rule_id: str) -> tuple[TriggerAction, ...]:
    if not isinstance(payload, list) or not payload:
        raise IntegrationConfigError(f"Trigger '{rule_id}' must define a non-empty 'then' list.")

    actions: list[TriggerAction] = []
    for index, raw_action in enumerate(payload):
        if not isinstance(raw_action, dict):
            raise IntegrationConfigError(f"Trigger '{rule_id}' action at index {index} must be a mapping.")
        action_type = _require_string(raw_action, "type", index)
        if action_type == "stdout":
            actions.append(TriggerAction(action_type="stdout"))
            continue
        if action_type == "file_append":
            target = _require_string(raw_action, "path", index)
            actions.append(TriggerAction(action_type="file_append", target=target))
            continue
        if action_type == "webhook":
            target = _require_string(raw_action, "url", index)
            _validate_webhook_url(rule_id, target)
            method = raw_action.get("method", "POST")
            if not isinstance(method, str) or not method.strip():
                raise IntegrationConfigError(f"Trigger '{rule_id}' action '{action_type}' requires a valid 'method'.")
            normalized_method = method.strip().upper()
            if normalized_method not in SUPPORTED_WEBHOOK_METHODS:
                raise IntegrationConfigError(
                    f"Trigger '{rule_id}' action '{action_type}' uses unsupported method '{normalized_method}'."
                )
            actions.append(TriggerAction(action_type="webhook", target=target, method=normalized_method))
            continue
        if action_type == "mqtt_publish":
            host = _require_string(raw_action, "host", index)
            topic = _require_string(raw_action, "topic", index)
            port = int(raw_action.get("port", 1883))
            if port <= 0:
                raise IntegrationConfigError(f"Trigger '{rule_id}' action '{action_type}' field 'port' must be > 0.")
            actions.append(
                TriggerAction(
                    action_type="mqtt_publish",
                    target=topic,
                    mqtt_host=host,
                    mqtt_port=port,
                    mqtt_topic=topic,
                )
            )
            continue
        if action_type == "log":
            target = _optional_string(raw_action, "event", rule_id)
            actions.append(TriggerAction(action_type="log", target=target or "trigger_fired"))
            continue
        raise IntegrationConfigError(f"Trigger '{rule_id}' action type '{action_type}' is not supported.")

    return tuple(actions)


def _parse_integration_target(payload: object, index: int) -> IntegrationTarget:
    if not isinstance(payload, dict):
        raise IntegrationConfigError(f"Integration target at index {index} must be a mapping.")

    integration_id = _require_config_string(payload, "id", f"Integration target at index {index}")
    source = _require_config_string(payload, "source", f"Integration '{integration_id}'")
    if source not in SUPPORTED_INTEGRATION_SOURCES:
        raise IntegrationConfigError(
            f"Integration '{integration_id}' uses unsupported source '{source}'."
        )

    target_type = _require_config_string(payload, "type", f"Integration '{integration_id}'")
    if target_type not in SUPPORTED_INTEGRATION_TARGET_TYPES:
        raise IntegrationConfigError(
            f"Integration '{integration_id}' target type '{target_type}' is not supported."
        )

    enabled = _optional_bool(payload, "enabled", integration_id, default=True)
    target, method, mqtt_host, mqtt_port, mqtt_topic = _parse_integration_transport(
        integration_id,
        target_type,
        payload,
    )
    trigger_ids = _optional_string_list(payload, "trigger_ids", integration_id)
    event_types = _optional_string_list(payload, "event_types", integration_id)
    interval_seconds = _optional_numeric_field(payload, "interval_seconds", integration_id)
    if source == "status":
        if interval_seconds is None or interval_seconds <= 0:
            raise IntegrationConfigError(
                f"Integration '{integration_id}' field 'interval_seconds' must be > 0 for status targets."
            )
    elif interval_seconds is not None and interval_seconds <= 0:
        raise IntegrationConfigError(
            f"Integration '{integration_id}' field 'interval_seconds' must be > 0 when present."
        )

    if source == "event" and not event_types:
        raise IntegrationConfigError(
            f"Integration '{integration_id}' event source targets must define at least one event type."
        )
    if source == "trigger" and not trigger_ids:
        raise IntegrationConfigError(
            f"Integration '{integration_id}' trigger source targets must define at least one trigger id."
        )

    return IntegrationTarget(
        integration_id=integration_id,
        target_type=target_type,
        source=source,
        enabled=enabled,
        target=target,
        method=method,
        mqtt_host=mqtt_host,
        mqtt_port=mqtt_port,
        mqtt_topic=mqtt_topic,
        event_types=tuple(event_types),
        trigger_ids=tuple(trigger_ids),
        interval_seconds=interval_seconds,
    )


def _validate_condition_source(rule_id: str, source: str) -> None:
    if source in SUPPORTED_TRIGGER_DECISION_SOURCES or source == "event.event_type":
        return
    if source.startswith("temporal.metrics."):
        metric_name = source.removeprefix("temporal.metrics.")
        if metric_name in SUPPORTED_TEMPORAL_METRICS:
            return
    if source.startswith("event.metadata.") and source.removeprefix("event.metadata."):
        return
    raise IntegrationConfigError(f"Trigger '{rule_id}' field 'when.source' uses unsupported source '{source}'.")


def _validate_condition_operator(rule_id: str, operator: str) -> None:
    if operator in SUPPORTED_TRIGGER_OPERATORS:
        return
    raise IntegrationConfigError(f"Trigger '{rule_id}' field 'when.operator' uses unsupported operator '{operator}'.")


def _validate_webhook_url(rule_id: str, url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise IntegrationConfigError(
            f"Trigger '{rule_id}' action 'webhook' must use an absolute http(s) URL."
        )


def _parse_integration_transport(
    integration_id: str,
    target_type: str,
    payload: dict[str, object],
) -> tuple[str | None, str, str | None, int, str | None]:
    if target_type == "stdout":
        return (None, "POST", None, 1883, None)
    if target_type == "file_append":
        target = _require_config_string(payload, "path", f"Integration '{integration_id}'")
        return (target, "POST", None, 1883, None)
    if target_type == "log":
        event_name = _optional_string(payload, "event", integration_id)
        return (event_name or "integration_dispatch", "POST", None, 1883, None)
    if target_type == "webhook":
        target = _require_config_string(payload, "url", f"Integration '{integration_id}'")
        _validate_named_webhook_url(integration_id, target)
        method = payload.get("method", "POST")
        if not isinstance(method, str) or not method.strip():
            raise IntegrationConfigError(f"Integration '{integration_id}' requires a valid 'method'.")
        normalized_method = method.strip().upper()
        if normalized_method not in SUPPORTED_WEBHOOK_METHODS:
            raise IntegrationConfigError(
                f"Integration '{integration_id}' uses unsupported method '{normalized_method}'."
            )
        return (target, normalized_method, None, 1883, None)
    host = _require_config_string(payload, "host", f"Integration '{integration_id}'")
    topic = _require_config_string(payload, "topic", f"Integration '{integration_id}'")
    port = int(payload.get("port", 1883))
    if port <= 0:
        raise IntegrationConfigError(f"Integration '{integration_id}' field 'port' must be > 0.")
    return (topic, "POST", host, port, topic)


def _require_config_string(payload: dict[str, object], key: str, owner: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise IntegrationConfigError(f"{owner} must define a non-empty '{key}' field.")
    return value.strip()


def _optional_string_list(payload: dict[str, object], key: str, owner: str) -> tuple[str, ...]:
    if key not in payload:
        return ()
    value = payload.get(key)
    if not isinstance(value, list):
        raise IntegrationConfigError(f"Integration '{owner}' field '{key}' must be a list of strings.")
    parsed: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise IntegrationConfigError(f"Integration '{owner}' field '{key}' must contain non-empty strings.")
        parsed.append(item.strip())
    return tuple(parsed)


def _validate_named_webhook_url(integration_id: str, url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise IntegrationConfigError(
            f"Integration '{integration_id}' must use an absolute http(s) URL."
        )
