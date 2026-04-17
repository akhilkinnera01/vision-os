"""Tests for browser-backed workspace config editors."""

from __future__ import annotations

from pathlib import Path

from integrations import load_integration_config, load_trigger_config
from server.editors import IntegrationEditor, TriggerEditor, ZoneEditor
from server.models import WorkspaceManifest
from server.store import WorkspaceStore
from zones import load_zones


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


def test_integration_editor_forks_shared_paths_into_workspace_local_files_on_save(tmp_path: Path) -> None:
    shared_path = tmp_path / "profiles" / "integrations" / "workstation.yaml"
    shared_path.parent.mkdir(parents=True, exist_ok=True)
    original_body = "integrations: []\n"
    shared_path.write_text(original_body, encoding="utf-8")
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="video",
            source_ref="demo/sample.mp4",
            integrations_path=str(shared_path),
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

    assert Path(payload["path"]).name == "visionos.integrations.yaml"
    assert Path(payload["path"]).parent.name == "desk-a"
    assert shared_path.read_text(encoding="utf-8") == original_body


def test_trigger_editor_loads_existing_rules_from_workspace_config(tmp_path: Path) -> None:
    triggers_path = tmp_path / "visionos.triggers.yaml"
    triggers_path.write_text(
        "\n".join(
            [
                "triggers:",
                "  - id: focus-session",
                "    when:",
                "      source: decision.label",
                "      operator: equals",
                "      value: Focused Work",
                "      min_duration_seconds: 5",
                "    then:",
                "      - type: webhook",
                "        url: https://example.com/focus",
                "    cooldown_seconds: 15",
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
            triggers_path=str(triggers_path),
        )
    )

    payload = TriggerEditor(workspace_store).load("desk-a")

    assert payload["workspace_id"] == "desk-a"
    assert payload["path"] == str(triggers_path.resolve())
    assert payload["exists"] is True
    assert payload["rule_count"] == 1
    assert payload["rules"][0]["id"] == "focus-session"
    assert payload["rules"][0]["actions"][0]["type"] == "webhook"
    assert payload["rules"][0]["actions"][0]["destination"] == "https://example.com/focus"


def test_trigger_editor_saves_rules_and_updates_workspace_manifest(tmp_path: Path) -> None:
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

    payload = TriggerEditor(workspace_store).save(
        "desk-a",
        [
            {
                "id": "focus-session",
                "enabled": True,
                "source": "decision.label",
                "operator": "equals",
                "value_text": "Focused Work",
                "min_duration_seconds": 5,
                "cooldown_seconds": 15,
                "repeat_interval_seconds": None,
                "rearm_on_clear": True,
                "event_metadata_filters_text": "",
                "actions": [
                    {
                        "type": "file_append",
                        "destination": "out/focus-events.jsonl",
                    },
                    {
                        "type": "webhook",
                        "destination": "https://example.com/focus",
                        "method": "POST",
                    },
                ],
            }
        ],
    )

    saved_workspace = workspace_store.get_workspace("desk-a")
    assert saved_workspace is not None
    assert saved_workspace.triggers_path == payload["path"]
    assert payload["exists"] is True
    assert payload["saved"] is True
    assert payload["rule_count"] == 1
    saved_config = load_trigger_config(payload["path"])
    assert saved_config.rules[0].rule_id == "focus-session"
    assert saved_config.rules[0].condition.min_duration_seconds == 5.0
    assert [action.action_type for action in saved_config.rules[0].actions] == ["file_append", "webhook"]


def test_trigger_editor_forks_shared_paths_into_workspace_local_files_on_save(tmp_path: Path) -> None:
    shared_path = tmp_path / "profiles" / "triggers" / "workstation.yaml"
    shared_path.parent.mkdir(parents=True, exist_ok=True)
    original_body = "triggers: []\n"
    shared_path.write_text(original_body, encoding="utf-8")
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="video",
            source_ref="demo/sample.mp4",
            triggers_path=str(shared_path),
        )
    )

    payload = TriggerEditor(workspace_store).save(
        "desk-a",
        [
            {
                "id": "focus-session",
                "enabled": True,
                "source": "decision.label",
                "operator": "equals",
                "value_text": "Focused Work",
                "min_duration_seconds": 5,
                "cooldown_seconds": 15,
                "repeat_interval_seconds": None,
                "rearm_on_clear": True,
                "event_metadata_filters_text": "",
                "actions": [{"type": "stdout"}],
            }
        ],
    )

    assert Path(payload["path"]).name == "visionos.triggers.yaml"
    assert Path(payload["path"]).parent.name == "desk-a"
    assert shared_path.read_text(encoding="utf-8") == original_body


def test_zone_editor_loads_existing_zones_from_workspace_config(tmp_path: Path) -> None:
    zones_path = tmp_path / "visionos.zones.yaml"
    zones_path.write_text(
        "\n".join(
            [
                "zones:",
                "  - id: desk_a",
                "    name: Desk A",
                "    type: occupancy",
                "    polygon:",
                "      - [40, 220]",
                "      - [320, 220]",
                "      - [320, 520]",
                "      - [40, 520]",
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
            zones_path=str(zones_path),
        )
    )

    payload = ZoneEditor(workspace_store).load("desk-a")

    assert payload["workspace_id"] == "desk-a"
    assert payload["path"] == str(zones_path.resolve())
    assert payload["exists"] is True
    assert payload["zone_count"] == 1
    assert payload["zones"][0]["id"] == "desk_a"
    assert payload["zones"][0]["polygon_text"] == "40,220\n320,220\n320,520\n40,520"


def test_zone_editor_saves_zones_and_updates_workspace_manifest(tmp_path: Path) -> None:
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

    payload = ZoneEditor(workspace_store).save(
        "desk-a",
        [
            {
                "id": "desk_a",
                "name": "Desk A",
                "type": "occupancy",
                "enabled": True,
                "profile": "",
                "labels_of_interest_text": "person, laptop",
                "polygon_text": "40,220\n320,220\n320,520\n40,520",
            }
        ],
    )

    saved_workspace = workspace_store.get_workspace("desk-a")
    assert saved_workspace is not None
    assert saved_workspace.zones_path == payload["path"]
    assert payload["exists"] is True
    assert payload["saved"] is True
    assert payload["zone_count"] == 1
    saved_zones = load_zones(payload["path"])
    assert saved_zones[0].zone_id == "desk_a"
    assert saved_zones[0].labels_of_interest == ("person", "laptop")


def test_zone_editor_forks_shared_paths_into_workspace_local_files_on_save(tmp_path: Path) -> None:
    shared_path = tmp_path / "profiles" / "zones" / "workstation.yaml"
    shared_path.parent.mkdir(parents=True, exist_ok=True)
    original_body = "zones: []\n"
    shared_path.write_text(original_body, encoding="utf-8")
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="video",
            source_ref="demo/sample.mp4",
            zones_path=str(shared_path),
        )
    )

    payload = ZoneEditor(workspace_store).save(
        "desk-a",
        [
            {
                "id": "desk_a",
                "name": "Desk A",
                "type": "occupancy",
                "enabled": True,
                "profile": "",
                "labels_of_interest_text": "",
                "polygon_text": "40,220\n320,220\n320,520\n40,520",
            }
        ],
    )

    assert Path(payload["path"]).name == "visionos.zones.yaml"
    assert Path(payload["path"]).parent.name == "desk-a"
    assert shared_path.read_text(encoding="utf-8") == original_body
