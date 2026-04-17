"""File-backed workspace editors for browser-managed config surfaces."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import yaml

from integrations import IntegrationConfig, IntegrationConfigError, IntegrationTarget, load_integration_config
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
        path = self._resolve_path(workspace)
        if not path.is_file():
            return self._payload(workspace, path, ())
        config = load_integration_config(str(path))
        return self._payload(workspace, path, config.targets, exists=True)

    def save(self, workspace_id: str, targets: object) -> dict[str, object]:
        workspace = self._require_workspace(workspace_id)
        path = self._resolve_path(workspace)
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

    def _resolve_path(self, workspace: WorkspaceManifest) -> Path:
        if workspace.integrations_path:
            return Path(workspace.integrations_path).resolve()
        if workspace.config_path:
            config_path = Path(workspace.config_path).resolve()
            return config_path.with_name(_replace_config_suffix(config_path.name, "integrations"))
        return (self.workspace_store.path.parent / "workspaces" / workspace.workspace_id / "visionos.integrations.yaml").resolve()

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
