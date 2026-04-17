"""Tests for Launchpad data assembly and the local browser app shell."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from server.launchpad import LaunchpadService
from server.models import SessionRecord, SessionSnapshot, ValidationRecord, WorkspaceManifest
from server.store import LiveStateStore, SessionStore, ValidationStore, WorkspaceStore
from server.web import LaunchpadApp


def test_launchpad_service_merges_workspace_validation_and_recent_sessions(tmp_path: Path) -> None:
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="webcam",
            profile_id="workstation",
        )
    )
    session_store.append_session(
        SessionRecord(
            session_id="session-2",
            workspace_id="desk-a",
            state="completed",
            started_at=20.0,
            ended_at=25.0,
        )
    )
    validation_store.save_result(
        ValidationRecord(
            workspace_id="desk-a",
            status="ok",
            checked_at=22.0,
            summary="Ready for live run",
        )
    )

    snapshot = LaunchpadService(workspace_store, session_store, validation_store).build_snapshot()

    assert snapshot["workspace_count"] == 1
    assert snapshot["workspaces"][0]["workspace_id"] == "desk-a"
    assert snapshot["workspaces"][0]["validation_state"] == "ok"
    assert snapshot["workspaces"][0]["last_run_state"] == "completed"
    assert snapshot["recent_sessions"][0]["workspace_name"] == "Desk A"


def test_launchpad_app_renders_launchpad_html(tmp_path: Path) -> None:
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="meeting-room",
            name="Meeting Room East",
            source_mode="video",
            profile_id="meeting_room",
        )
    )
    app = LaunchpadApp(LaunchpadService(workspace_store, session_store, validation_store))

    status, headers, body = _call_app(app, "/")

    assert status == "200 OK"
    assert ("Content-Type", "text/html; charset=utf-8") in headers
    assert "Vision OS Launchpad" in body
    assert "Meeting Room East" in body
    assert "Run Setup" in body


def test_launchpad_app_returns_json_snapshot(tmp_path: Path) -> None:
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    app = LaunchpadApp(LaunchpadService(workspace_store, session_store, validation_store))

    status, headers, body = _call_app(app, "/api/launchpad")

    assert status == "200 OK"
    assert ("Content-Type", "application/json; charset=utf-8") in headers
    assert '"workspace_count": 0' in body
    assert '"recent_sessions": []' in body


def test_launchpad_app_renders_workspace_shell_page(tmp_path: Path) -> None:
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="lab-bench-3",
            name="Lab Bench 3",
            source_mode="webcam",
            profile_id="lab_bench",
        )
    )
    app = LaunchpadApp(LaunchpadService(workspace_store, session_store, validation_store))

    status, headers, body = _call_app(app, "/workspaces/lab-bench-3")

    assert status == "200 OK"
    assert ("Content-Type", "text/html; charset=utf-8") in headers
    assert "Lab Bench 3" in body
    assert "Live" in body
    assert "Integrations" in body
    assert "Validate" in body
    assert "Start + Record" in body
    assert "Save zones" in body
    assert "Save triggers" in body
    assert "Save integrations" in body


def test_launchpad_app_returns_live_workspace_snapshot(tmp_path: Path) -> None:
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    live_state_store = LiveStateStore(tmp_path / "live")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="webcam",
        )
    )
    live_state_store.save_snapshot(
        SessionSnapshot(
            session_id="session-1",
            workspace_id="desk-a",
            state="running",
            scene_label="Focused Work",
            explanation="Laptop near seated person",
            metrics={"fps": 14.5},
            recent_events=("focus_started",),
        )
    )
    app = LaunchpadApp(
        LaunchpadService(workspace_store, session_store, validation_store),
        live_state_store=live_state_store,
    )

    status, headers, body = _call_app(app, "/api/workspaces/desk-a/live")

    assert status == "200 OK"
    assert ("Content-Type", "application/json; charset=utf-8") in headers
    assert '"active": true' in body
    assert '"scene_label": "Focused Work"' in body


def test_launchpad_app_returns_preview_bytes_for_active_workspace(tmp_path: Path) -> None:
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    live_state_store = LiveStateStore(tmp_path / "live")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="webcam",
        )
    )
    live_state_store.save_snapshot(
        SessionSnapshot(
            session_id="session-1",
            workspace_id="desk-a",
            state="running",
        )
    )
    live_state_store.save_preview(b"jpeg-payload")
    app = LaunchpadApp(
        LaunchpadService(workspace_store, session_store, validation_store),
        live_state_store=live_state_store,
    )

    status, headers, body = _call_app_raw(app, "/api/workspaces/desk-a/preview")

    assert status == "200 OK"
    assert ("Content-Type", "image/jpeg") in headers
    assert body == b"jpeg-payload"


def test_launchpad_app_starts_a_workspace_through_the_runtime_host(tmp_path: Path) -> None:
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    calls = []
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="webcam",
        )
    )
    service = LaunchpadService(
        workspace_store,
        session_store,
        validation_store,
        runtime_host=SimpleNamespace(
            is_running=False,
            active_workspace_id=None,
            start=lambda *, workspace, record_replay=False: calls.append((workspace.workspace_id, record_replay)) or setattr(service.runtime_host, "active_workspace_id", workspace.workspace_id),
            stop=lambda: None,
        ),
    )
    app = LaunchpadApp(service)

    status, headers, body = _call_app(app, "/api/workspaces/desk-a/start", method="POST")

    assert status == "200 OK"
    assert ("Content-Type", "application/json; charset=utf-8") in headers
    assert calls == [("desk-a", False)]
    assert '"started": true' in body


def test_launchpad_app_stops_the_active_runtime_workspace(tmp_path: Path) -> None:
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    captured = {"stopped": False}
    runtime_host = SimpleNamespace(
        is_running=True,
        active_workspace_id="desk-a",
        start=lambda *, workspace: None,
        stop=lambda: captured.update({"stopped": True}) or setattr(runtime_host, "active_workspace_id", None),
    )
    app = LaunchpadApp(LaunchpadService(workspace_store, session_store, validation_store, runtime_host=runtime_host))

    status, headers, body = _call_app(app, "/api/runtime/stop", method="POST")

    assert status == "200 OK"
    assert ("Content-Type", "application/json; charset=utf-8") in headers
    assert captured["stopped"] is True
    assert '"stopped": true' in body


def test_launchpad_app_starts_a_workspace_with_recording(tmp_path: Path) -> None:
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    captured = {}
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="video",
            source_ref="demo/sample.mp4",
        )
    )
    service = LaunchpadService(
        workspace_store,
        session_store,
        validation_store,
        runtime_host=SimpleNamespace(
            is_running=False,
            active_workspace_id=None,
            active_record_path=None,
            start=lambda *, workspace, record_replay=False: captured.update(
                {"workspace_id": workspace.workspace_id, "record_replay": record_replay}
            ) or setattr(service.runtime_host, "active_workspace_id", workspace.workspace_id) or setattr(
                service.runtime_host, "active_record_path", ".visionos/artifacts/desk-a-recording-1.jsonl"
            ) or ".visionos/artifacts/desk-a-recording-1.jsonl",
            stop=lambda: None,
        ),
    )
    app = LaunchpadApp(service)

    status, headers, body = _call_app(app, "/api/workspaces/desk-a/start-recording", method="POST")

    assert status == "200 OK"
    assert ("Content-Type", "application/json; charset=utf-8") in headers
    assert captured == {"workspace_id": "desk-a", "record_replay": True}
    assert '"record_path": ".visionos/artifacts/desk-a-recording-1.jsonl"' in body


def test_launchpad_app_validates_a_workspace_through_the_service(tmp_path: Path) -> None:
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    captured = {}
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="webcam",
        )
    )
    service = LaunchpadService(
        workspace_store,
        session_store,
        validation_store,
        validator=lambda workspace: captured.update({"workspace_id": workspace.workspace_id}) or {
            "workspace_id": workspace.workspace_id,
            "status": "ok",
            "summary": "Camera ready",
            "checks": [{"name": "source", "status": "ok", "detail": "Camera ready"}],
        },
    )
    app = LaunchpadApp(service)

    status, headers, body = _call_app(app, "/api/workspaces/desk-a/validate", method="POST")

    assert status == "200 OK"
    assert ("Content-Type", "application/json; charset=utf-8") in headers
    assert captured["workspace_id"] == "desk-a"
    assert '"summary": "Camera ready"' in body


def test_launchpad_app_returns_workspace_integrations_payload(tmp_path: Path) -> None:
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
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="video",
            source_ref="demo/sample.mp4",
            integrations_path=str(integrations_path),
        )
    )
    app = LaunchpadApp(LaunchpadService(workspace_store, session_store, validation_store))

    status, headers, body = _call_app(app, "/api/workspaces/desk-a/integrations")

    assert status == "200 OK"
    assert ("Content-Type", "application/json; charset=utf-8") in headers
    assert '"target_count": 1' in body
    assert '"id": "focus-hook"' in body


def test_launchpad_app_saves_workspace_integrations_payload(tmp_path: Path) -> None:
    config_path = tmp_path / "visionos.config.yaml"
    config_path.write_text("source: video\ninput: demo/sample.mp4\n", encoding="utf-8")
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="video",
            source_ref="demo/sample.mp4",
            config_path=str(config_path),
        )
    )
    app = LaunchpadApp(LaunchpadService(workspace_store, session_store, validation_store))

    status, headers, body = _call_app(
        app,
        "/api/workspaces/desk-a/integrations",
        method="POST",
        payload={
            "targets": [
                {
                    "id": "status-log",
                    "type": "log",
                    "source": "status",
                    "enabled": True,
                    "destination": "room_status_dispatch",
                    "interval_seconds": 5,
                }
            ]
        },
    )

    assert status == "200 OK"
    assert ("Content-Type", "application/json; charset=utf-8") in headers
    assert '"saved": true' in body
    assert '"target_count": 1' in body
    saved_workspace = workspace_store.get_workspace("desk-a")
    assert saved_workspace is not None
    assert saved_workspace.integrations_path is not None
    assert Path(saved_workspace.integrations_path).is_file()


def test_launchpad_app_returns_workspace_trigger_payload(tmp_path: Path) -> None:
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
                "    then:",
                "      - type: stdout",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="video",
            source_ref="demo/sample.mp4",
            triggers_path=str(triggers_path),
        )
    )
    app = LaunchpadApp(LaunchpadService(workspace_store, session_store, validation_store))

    status, headers, body = _call_app(app, "/api/workspaces/desk-a/triggers")

    assert status == "200 OK"
    assert ("Content-Type", "application/json; charset=utf-8") in headers
    assert '"rule_count": 1' in body
    assert '"id": "focus-session"' in body


def test_launchpad_app_saves_workspace_trigger_payload(tmp_path: Path) -> None:
    config_path = tmp_path / "visionos.config.yaml"
    config_path.write_text("source: video\ninput: demo/sample.mp4\n", encoding="utf-8")
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="video",
            source_ref="demo/sample.mp4",
            config_path=str(config_path),
        )
    )
    app = LaunchpadApp(LaunchpadService(workspace_store, session_store, validation_store))

    status, headers, body = _call_app(
        app,
        "/api/workspaces/desk-a/triggers",
        method="POST",
        payload={
            "rules": [
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
                        {"type": "stdout"},
                    ],
                }
            ]
        },
    )

    assert status == "200 OK"
    assert ("Content-Type", "application/json; charset=utf-8") in headers
    assert '"saved": true' in body
    assert '"rule_count": 1' in body
    saved_workspace = workspace_store.get_workspace("desk-a")
    assert saved_workspace is not None
    assert saved_workspace.triggers_path is not None
    assert Path(saved_workspace.triggers_path).is_file()


def test_launchpad_app_returns_workspace_zone_payload(tmp_path: Path) -> None:
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
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="video",
            source_ref="demo/sample.mp4",
            zones_path=str(zones_path),
        )
    )
    app = LaunchpadApp(LaunchpadService(workspace_store, session_store, validation_store))

    status, headers, body = _call_app(app, "/api/workspaces/desk-a/zones")

    assert status == "200 OK"
    assert ("Content-Type", "application/json; charset=utf-8") in headers
    assert '"zone_count": 1' in body
    assert '"id": "desk_a"' in body


def test_launchpad_app_saves_workspace_zone_payload(tmp_path: Path) -> None:
    config_path = tmp_path / "visionos.config.yaml"
    config_path.write_text("source: video\ninput: demo/sample.mp4\n", encoding="utf-8")
    workspace_store = WorkspaceStore(tmp_path / "workspaces.json")
    session_store = SessionStore(tmp_path / "sessions.json")
    validation_store = ValidationStore(tmp_path / "validations.json")
    workspace_store.save_workspace(
        WorkspaceManifest(
            workspace_id="desk-a",
            name="Desk A",
            source_mode="video",
            source_ref="demo/sample.mp4",
            config_path=str(config_path),
        )
    )
    app = LaunchpadApp(LaunchpadService(workspace_store, session_store, validation_store))

    status, headers, body = _call_app(
        app,
        "/api/workspaces/desk-a/zones",
        method="POST",
        payload={
            "zones": [
                {
                    "id": "desk_a",
                    "name": "Desk A",
                    "type": "occupancy",
                    "enabled": True,
                    "profile": "",
                    "labels_of_interest_text": "person, laptop",
                    "polygon_text": "40,220\n320,220\n320,520\n40,520",
                }
            ]
        },
    )

    assert status == "200 OK"
    assert ("Content-Type", "application/json; charset=utf-8") in headers
    assert '"saved": true' in body
    assert '"zone_count": 1' in body
    saved_workspace = workspace_store.get_workspace("desk-a")
    assert saved_workspace is not None
    assert saved_workspace.zones_path is not None
    assert Path(saved_workspace.zones_path).is_file()


def _call_app(
    app: LaunchpadApp,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> tuple[str, list[tuple[str, str]], str]:
    status, headers, body = _call_app_raw(app, path, method=method, payload=payload)
    return status, headers, body.decode("utf-8")


def _call_app_raw(
    app: LaunchpadApp,
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
) -> tuple[str, list[tuple[str, str]], bytes]:
    captured: dict[str, object] = {}
    request_body = b"" if payload is None else json.dumps(payload).encode("utf-8")

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "127.0.0.1",
        "SERVER_PORT": "8765",
        "CONTENT_LENGTH": str(len(request_body)),
        "CONTENT_TYPE": "application/json",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": BytesIO(request_body),
        "wsgi.errors": BytesIO(),
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
    }

    body = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], body
