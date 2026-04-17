"""File-backed workspace editors for browser-managed config surfaces."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path

import yaml

from integrations import (
    IntegrationConfig,
    IntegrationConfigError,
    IntegrationTarget,
    TriggerAction,
    TriggerConfig,
    TriggerRule,
    load_integration_config,
    load_trigger_config,
)
from server.models import WorkspaceManifest
from server.store import WorkspaceStore


class WorkspaceEditorError(ValueError):
    """Raised when a browser-backed workspace editor payload is malformed."""


class IntegrationEditor:
    """Load and save integration targets for the browser workspace shell."""

    def __init__(self, workspace_store: WorkspaceStore) -> None:
        self.workspace_store = workspace_store

    def load(self, workspace_id: str) -> dict[str, object]:
        workspace = self._require_workspace(workspace_id)
        path = self._load_path(workspace)
        if not path.is_file():
            return self._payload(workspace, path, ())
        config = load_integration_config(str(path))
        return self._payload(workspace, path, config.targets, exists=True)

    def save(self, workspace_id: str, targets: object) -> dict[str, object]:
        workspace = self._require_workspace(workspace_id)
        path = self._save_path(workspace)
        config = self._validate_targets(targets, path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._serialize_config(config), encoding="utf-8")
        if workspace.integrations_path != str(path):
            self.workspace_store.save_workspace(replace(workspace, integrations_path=str(path)))
            workspace = self._require_workspace(workspace_id)
        return {
            **self._payload(workspace, path, config.targets, exists=True),
            "saved": True,
            "summary": f"Saved {len(config.targets)} integration target{'s' if len(config.targets) != 1 else ''}.",
        }

    def _payload(
        self,
        workspace: WorkspaceManifest,
        path: Path,
        targets: tuple[IntegrationTarget, ...],
        *,
        exists: bool = False,
    ) -> dict[str, object]:
        return {
            "workspace_id": workspace.workspace_id,
            "path": str(path),
            "exists": exists,
            "target_count": len(targets),
            "targets": [self._target_to_editor_item(target) for target in targets],
        }

    def _require_workspace(self, workspace_id: str) -> WorkspaceManifest:
        workspace = self.workspace_store.get_workspace(workspace_id)
        if workspace is None:
            raise KeyError(workspace_id)
        return workspace

    def _load_path(self, workspace: WorkspaceManifest) -> Path:
        return _resolve_workspace_editor_load_path(
            self.workspace_store,
            workspace,
            explicit_path=workspace.integrations_path,
            kind="integrations",
        )

    def _save_path(self, workspace: WorkspaceManifest) -> Path:
        return _resolve_workspace_editor_save_path(
            self.workspace_store,
            workspace,
            explicit_path=workspace.integrations_path,
            kind="integrations",
        )

    def _validate_targets(self, targets: object, path: Path) -> IntegrationConfig:
        if not isinstance(targets, list):
            raise WorkspaceEditorError("Integration editor payload must define a 'targets' list.")
        serialized_targets = [self._editor_item_to_yaml_target(item) for item in targets]
        payload = {"integrations": serialized_targets}
        temp_path = path.with_name(f".{path.name}.tmp")
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        try:
            return load_integration_config(str(temp_path))
        except IntegrationConfigError as exc:
            raise WorkspaceEditorError(str(exc)) from exc
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _editor_item_to_yaml_target(self, item: object) -> dict[str, object]:
        if not isinstance(item, dict):
            raise WorkspaceEditorError("Integration targets must be objects.")

        target_id = _require_editor_string(item.get("id"), "Integration target id")
        target_type = _require_editor_string(item.get("type"), f"Integration '{target_id}' type")
        source = _require_editor_string(item.get("source"), f"Integration '{target_id}' source")
        enabled = bool(item.get("enabled", True))
        payload: dict[str, object] = {
            "id": target_id,
            "type": target_type,
            "source": source,
        }
        if not enabled:
            payload["enabled"] = False

        destination = _optional_editor_string(item.get("destination"))
        method = _optional_editor_string(item.get("method"))
        mqtt_host = _optional_editor_string(item.get("mqtt_host"))
        mqtt_topic = _optional_editor_string(item.get("mqtt_topic"))
        mqtt_port = _optional_editor_int(item.get("mqtt_port"))
        interval_seconds = _optional_editor_float(item.get("interval_seconds"))
        event_types = _coerce_editor_string_list(item.get("event_types"))
        trigger_ids = _coerce_editor_string_list(item.get("trigger_ids"))

        if target_type == "file_append":
            payload["path"] = _require_editor_string(destination, f"Integration '{target_id}' path")
        elif target_type == "log":
            if destination:
                payload["event"] = destination
        elif target_type == "webhook":
            payload["url"] = _require_editor_string(destination, f"Integration '{target_id}' url")
            if method:
                payload["method"] = method
        elif target_type == "mqtt_publish":
            payload["host"] = _require_editor_string(mqtt_host, f"Integration '{target_id}' host")
            payload["topic"] = _require_editor_string(mqtt_topic, f"Integration '{target_id}' topic")
            if mqtt_port is not None:
                payload["port"] = mqtt_port

        if source == "event" and event_types:
            payload["event_types"] = event_types
        if source == "trigger" and trigger_ids:
            payload["trigger_ids"] = trigger_ids
        if interval_seconds is not None:
            payload["interval_seconds"] = interval_seconds
        return payload

    def _serialize_config(self, config: IntegrationConfig) -> str:
        payload = {
            "integrations": [self._serialize_target(target) for target in config.targets],
        }
        return yaml.safe_dump(payload, sort_keys=False)

    def _serialize_target(self, target: IntegrationTarget) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": target.integration_id,
            "type": target.target_type,
            "source": target.source,
        }
        if not target.enabled:
            payload["enabled"] = False
        if target.target_type == "file_append" and target.target is not None:
            payload["path"] = target.target
        elif target.target_type == "log" and target.target is not None:
            payload["event"] = target.target
        elif target.target_type == "webhook" and target.target is not None:
            payload["url"] = target.target
            if target.method != "POST":
                payload["method"] = target.method
        elif target.target_type == "mqtt_publish":
            if target.mqtt_host is not None:
                payload["host"] = target.mqtt_host
            if target.mqtt_topic is not None:
                payload["topic"] = target.mqtt_topic
            if target.mqtt_port != 1883:
                payload["port"] = target.mqtt_port

        if target.source == "event" and target.event_types:
            payload["event_types"] = list(target.event_types)
        if target.source == "trigger" and target.trigger_ids:
            payload["trigger_ids"] = list(target.trigger_ids)
        if target.interval_seconds is not None:
            payload["interval_seconds"] = target.interval_seconds
        return payload

    def _target_to_editor_item(self, target: IntegrationTarget) -> dict[str, object]:
        destination = None
        if target.target_type in {"file_append", "log", "webhook"}:
            destination = target.target
        return {
            "id": target.integration_id,
            "type": target.target_type,
            "source": target.source,
            "enabled": target.enabled,
            "destination": destination,
            "method": target.method,
            "mqtt_host": target.mqtt_host,
            "mqtt_port": target.mqtt_port,
            "mqtt_topic": target.mqtt_topic,
            "event_types": list(target.event_types),
            "trigger_ids": list(target.trigger_ids),
            "interval_seconds": target.interval_seconds,
        }


class TriggerEditor:
    """Load and save trigger rules for the browser workspace shell."""

    def __init__(self, workspace_store: WorkspaceStore) -> None:
        self.workspace_store = workspace_store

    def load(self, workspace_id: str) -> dict[str, object]:
        workspace = self._require_workspace(workspace_id)
        path = self._load_path(workspace)
        if not path.is_file():
            return self._payload(workspace, path, ())
        config = load_trigger_config(str(path))
        return self._payload(workspace, path, config.rules, exists=True)

    def save(self, workspace_id: str, rules: object) -> dict[str, object]:
        workspace = self._require_workspace(workspace_id)
        path = self._save_path(workspace)
        config = self._validate_rules(rules, path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self._serialize_config(config), encoding="utf-8")
        if workspace.triggers_path != str(path):
            self.workspace_store.save_workspace(replace(workspace, triggers_path=str(path)))
            workspace = self._require_workspace(workspace_id)
        return {
            **self._payload(workspace, path, config.rules, exists=True),
            "saved": True,
            "summary": f"Saved {len(config.rules)} trigger rule{'s' if len(config.rules) != 1 else ''}.",
        }

    def _payload(
        self,
        workspace: WorkspaceManifest,
        path: Path,
        rules: tuple[TriggerRule, ...],
        *,
        exists: bool = False,
    ) -> dict[str, object]:
        return {
            "workspace_id": workspace.workspace_id,
            "path": str(path),
            "exists": exists,
            "rule_count": len(rules),
            "rules": [self._rule_to_editor_item(rule) for rule in rules],
        }

    def _require_workspace(self, workspace_id: str) -> WorkspaceManifest:
        workspace = self.workspace_store.get_workspace(workspace_id)
        if workspace is None:
            raise KeyError(workspace_id)
        return workspace

    def _load_path(self, workspace: WorkspaceManifest) -> Path:
        return _resolve_workspace_editor_load_path(
            self.workspace_store,
            workspace,
            explicit_path=workspace.triggers_path,
            kind="triggers",
        )

    def _save_path(self, workspace: WorkspaceManifest) -> Path:
        return _resolve_workspace_editor_save_path(
            self.workspace_store,
            workspace,
            explicit_path=workspace.triggers_path,
            kind="triggers",
        )

    def _validate_rules(self, rules: object, path: Path) -> TriggerConfig:
        if not isinstance(rules, list):
            raise WorkspaceEditorError("Trigger editor payload must define a 'rules' list.")
        serialized_rules = [self._editor_item_to_yaml_rule(item) for item in rules]
        payload = {"triggers": serialized_rules}
        temp_path = path.with_name(f".{path.name}.tmp")
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        try:
            return load_trigger_config(str(temp_path))
        except IntegrationConfigError as exc:
            raise WorkspaceEditorError(str(exc)) from exc
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _editor_item_to_yaml_rule(self, item: object) -> dict[str, object]:
        if not isinstance(item, dict):
            raise WorkspaceEditorError("Trigger rules must be objects.")

        rule_id = _require_editor_string(item.get("id"), "Trigger rule id")
        source = _require_editor_string(item.get("source"), f"Trigger '{rule_id}' source")
        operator = _require_editor_string(item.get("operator"), f"Trigger '{rule_id}' operator")
        value_text = _require_editor_string(item.get("value_text"), f"Trigger '{rule_id}' value")
        enabled = bool(item.get("enabled", True))
        min_duration_seconds = _optional_editor_float(item.get("min_duration_seconds"))
        cooldown_seconds = _optional_editor_float(item.get("cooldown_seconds"))
        repeat_interval_seconds = _optional_editor_float(item.get("repeat_interval_seconds"))
        rearm_on_clear = bool(item.get("rearm_on_clear", True))
        actions = item.get("actions", [])
        if not isinstance(actions, list):
            raise WorkspaceEditorError("Trigger actions must be a list.")

        payload: dict[str, object] = {
            "id": rule_id,
            "when": {
                "source": source,
                "operator": operator,
                "value": _parse_trigger_value(value_text),
            },
            "then": [self._editor_action_to_yaml_action(rule_id, action) for action in actions],
        }
        if not enabled:
            payload["enabled"] = False
        if min_duration_seconds is not None:
            payload["when"]["min_duration_seconds"] = min_duration_seconds
        metadata_filters = _parse_metadata_filters(item.get("event_metadata_filters_text"))
        if metadata_filters:
            payload["when"]["event_metadata_filters"] = metadata_filters
        if cooldown_seconds is not None:
            payload["cooldown_seconds"] = cooldown_seconds
        if repeat_interval_seconds is not None:
            payload["repeat_interval_seconds"] = repeat_interval_seconds
        if not rearm_on_clear:
            payload["rearm_on_clear"] = False
        return payload

    def _editor_action_to_yaml_action(self, rule_id: str, action: object) -> dict[str, object]:
        if not isinstance(action, dict):
            raise WorkspaceEditorError(f"Trigger '{rule_id}' actions must be objects.")
        action_type = _require_editor_string(action.get("type"), f"Trigger '{rule_id}' action type")
        payload: dict[str, object] = {"type": action_type}
        destination = _optional_editor_string(action.get("destination"))
        method = _optional_editor_string(action.get("method"))
        mqtt_host = _optional_editor_string(action.get("mqtt_host"))
        mqtt_topic = _optional_editor_string(action.get("mqtt_topic"))
        mqtt_port = _optional_editor_int(action.get("mqtt_port"))

        if action_type == "file_append":
            payload["path"] = _require_editor_string(destination, f"Trigger '{rule_id}' file action path")
        elif action_type == "log":
            if destination:
                payload["event"] = destination
        elif action_type == "webhook":
            payload["url"] = _require_editor_string(destination, f"Trigger '{rule_id}' webhook url")
            if method:
                payload["method"] = method
        elif action_type == "mqtt_publish":
            payload["host"] = _require_editor_string(mqtt_host, f"Trigger '{rule_id}' MQTT host")
            payload["topic"] = _require_editor_string(mqtt_topic, f"Trigger '{rule_id}' MQTT topic")
            if mqtt_port is not None:
                payload["port"] = mqtt_port
        return payload

    def _serialize_config(self, config: TriggerConfig) -> str:
        payload = {
            "triggers": [self._serialize_rule(rule) for rule in config.rules],
        }
        return yaml.safe_dump(payload, sort_keys=False)

    def _serialize_rule(self, rule: TriggerRule) -> dict[str, object]:
        assert rule.condition is not None
        payload: dict[str, object] = {
            "id": rule.rule_id,
            "when": {
                "source": rule.condition.source,
                "operator": rule.condition.operator,
                "value": rule.condition.value,
            },
            "then": [self._serialize_action(action) for action in rule.actions],
        }
        if not rule.enabled:
            payload["enabled"] = False
        if rule.condition.min_duration_seconds > 0:
            payload["when"]["min_duration_seconds"] = rule.condition.min_duration_seconds
        if rule.condition.event_metadata_filters:
            payload["when"]["event_metadata_filters"] = dict(rule.condition.event_metadata_filters)
        if rule.cooldown_seconds > 0:
            payload["cooldown_seconds"] = rule.cooldown_seconds
        if rule.repeat_interval_seconds is not None:
            payload["repeat_interval_seconds"] = rule.repeat_interval_seconds
        if not rule.rearm_on_clear:
            payload["rearm_on_clear"] = False
        return payload

    def _serialize_action(self, action: TriggerAction) -> dict[str, object]:
        payload: dict[str, object] = {"type": action.action_type}
        if action.action_type == "file_append" and action.target is not None:
            payload["path"] = action.target
        elif action.action_type == "log" and action.target is not None:
            payload["event"] = action.target
        elif action.action_type == "webhook" and action.target is not None:
            payload["url"] = action.target
            if action.method != "POST":
                payload["method"] = action.method
        elif action.action_type == "mqtt_publish":
            if action.mqtt_host is not None:
                payload["host"] = action.mqtt_host
            if action.mqtt_topic is not None:
                payload["topic"] = action.mqtt_topic
            if action.mqtt_port != 1883:
                payload["port"] = action.mqtt_port
        return payload

    def _rule_to_editor_item(self, rule: TriggerRule) -> dict[str, object]:
        assert rule.condition is not None
        return {
            "id": rule.rule_id,
            "enabled": rule.enabled,
            "source": rule.condition.source,
            "operator": rule.condition.operator,
            "value_text": _format_trigger_value(rule.condition.value),
            "min_duration_seconds": rule.condition.min_duration_seconds,
            "cooldown_seconds": rule.cooldown_seconds,
            "repeat_interval_seconds": rule.repeat_interval_seconds,
            "rearm_on_clear": rule.rearm_on_clear,
            "event_metadata_filters_text": (
                json.dumps(rule.condition.event_metadata_filters, sort_keys=True)
                if rule.condition.event_metadata_filters
                else ""
            ),
            "actions": [self._action_to_editor_item(action) for action in rule.actions],
        }

    def _action_to_editor_item(self, action: TriggerAction) -> dict[str, object]:
        destination = None
        if action.action_type in {"file_append", "log", "webhook"}:
            destination = action.target
        return {
            "type": action.action_type,
            "destination": destination,
            "method": action.method,
            "mqtt_host": action.mqtt_host,
            "mqtt_port": action.mqtt_port,
            "mqtt_topic": action.mqtt_topic,
        }


def _resolve_workspace_editor_load_path(
    workspace_store: WorkspaceStore,
    workspace: WorkspaceManifest,
    *,
    explicit_path: str | None,
    kind: str,
) -> Path:
    if explicit_path:
        return Path(explicit_path).resolve()
    return _workspace_owned_editor_path(workspace_store, workspace, kind)


def _resolve_workspace_editor_save_path(
    workspace_store: WorkspaceStore,
    workspace: WorkspaceManifest,
    *,
    explicit_path: str | None,
    kind: str,
) -> Path:
    generated_path = _workspace_owned_editor_path(workspace_store, workspace, kind)
    if explicit_path and Path(explicit_path).resolve() == generated_path:
        return generated_path
    return generated_path


def _workspace_owned_editor_path(
    workspace_store: WorkspaceStore,
    workspace: WorkspaceManifest,
    kind: str,
) -> Path:
    if workspace.config_path:
        config_path = Path(workspace.config_path).resolve()
        return config_path.with_name(_replace_config_suffix(config_path.name, kind))
    return (workspace_store.path.parent / "workspaces" / workspace.workspace_id / f"visionos.{kind}.yaml").resolve()


def _replace_config_suffix(filename: str, kind: str) -> str:
    if filename.endswith(".config.yaml"):
        return filename.replace(".config.yaml", f".{kind}.yaml")
    if filename.endswith(".config.yml"):
        return filename.replace(".config.yml", f".{kind}.yml")
    if filename.endswith(".yaml") or filename.endswith(".yml"):
        stem, _, suffix = filename.rpartition(".")
        return f"{stem}.{kind}.{suffix}"
    return f"{filename}.{kind}.yaml"


def _require_editor_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkspaceEditorError(f"{label} is required.")
    return value.strip()


def _optional_editor_string(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise WorkspaceEditorError("Integration editor string fields must be strings when present.")
    stripped = value.strip()
    return stripped or None


def _optional_editor_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise WorkspaceEditorError("Integration editor numeric fields must be numeric when present.")
    return int(value)


def _optional_editor_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise WorkspaceEditorError("Integration editor numeric fields must be numeric when present.")
    return float(value)


def _coerce_editor_string_list(value: object) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if not isinstance(value, list):
        raise WorkspaceEditorError("Integration editor list fields must be arrays or comma-separated strings.")
    parsed: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise WorkspaceEditorError("Integration editor list fields must contain non-empty strings.")
        parsed.append(item.strip())
    return parsed


def _parse_trigger_value(value: object) -> object:
    if isinstance(value, bool | int | float | list | dict):
        return value
    text = _require_editor_string(value, "Trigger value")
    lowered = text.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if text.startswith("{") or text.startswith("["):
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise WorkspaceEditorError("Trigger values that look like JSON must be valid JSON.") from exc
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


def _format_trigger_value(value: object) -> str:
    if isinstance(value, dict | list):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _parse_metadata_filters(value: object) -> dict[str, object]:
    if value in (None, ""):
        return {}
    text = _require_editor_string(value, "Trigger metadata filters")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise WorkspaceEditorError("Trigger metadata filters must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise WorkspaceEditorError("Trigger metadata filters must decode to an object.")
    return payload
