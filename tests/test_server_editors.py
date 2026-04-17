"""Tests for browser-backed workspace config editors."""

from __future__ import annotations

from pathlib import Path

from integrations import load_integration_config
from server.editors import IntegrationEditor
from server.models import WorkspaceManifest
from server.store import WorkspaceStore


def test_integration_editor_loads_existing_targets_from_workspace_config(tmp_path: Path) -> None:
    integrations_path = tmp_path / "visionos.integrations.yaml"
    integrations_path.write_text(
        "\n".join(
            [
                "integrations:",
                "  - id: focus-hook",
                "    type: webhook",
                "    source: trigger",
                "    trigger_ids:",
                "      - focus-sustained",
                "    url: https://example.com/focus",
                "    method: POST",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="video",
            source_ref="demo/sample.mp4",
            integrations_path=str(integrations_path),
        )
    )

    payload = IntegrationEditor(workspace_store).load("desk-a")

    assert payload["workspace_id"] == "desk-a"
    assert payload["path"] == str(integrations_path.resolve())
    assert payload["exists"] is True
    assert payload["target_count"] == 1
    assert payload["targets"] == [
        {
            "id": "focus-hook",
            "type": "webhook",
            "source": "trigger",
            "enabled": True,
            "destination": "https://example.com/focus",
            "method": "POST",
            "mqtt_host": None,
            "mqtt_port": 1883,
            "mqtt_topic": None,
            "event_types": [],
            "trigger_ids": ["focus-sustained"],
            "interval_seconds": None,
        }
    ]


def test_integration_editor_saves_targets_and_updates_workspace_manifest(tmp_path: Path) -> None:
    config_path = tmp_path / "visionos.config.yaml"
    config_path.write_text(
        "\n".join(
            [
                "source: video",
                "input: demo/sample.mp4",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="video",
            source_ref="demo/sample.mp4",
            config_path=str(config_path),
        )
    )

    payload = IntegrationEditor(workspace_store).save(
        "desk-a",
        [
            {
                "id": "status-log",
                "type": "log",
                "source": "status",
                "enabled": True,
                "destination": "room_status_dispatch",
                "interval_seconds": 5,
            }
        ],
    )

    saved_workspace = workspace_store.get_workspace("desk-a")
    assert saved_workspace is not None
    assert saved_workspace.integrations_path == payload["path"]
    assert payload["exists"] is True
    assert payload["saved"] is True
    assert payload["target_count"] == 1
    saved_config = load_integration_config(payload["path"])
    assert saved_config.targets[0].integration_id == "status-log"
    assert saved_config.targets[0].source == "status"
    assert saved_config.targets[0].interval_seconds == 5.0
