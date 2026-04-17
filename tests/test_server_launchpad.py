"""Tests for Launchpad data assembly and the local browser app shell."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from server.launchpad import LaunchpadService
from server.models import SessionRecord, ValidationRecord, WorkspaceManifest
from server.store import SessionStore, ValidationStore, WorkspaceStore
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


def _call_app(app: LaunchpadApp, path: str) -> tuple[str, list[tuple[str, str]], str]:
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    environ = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "SERVER_NAME": "127.0.0.1",
        "SERVER_PORT": "8765",
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "http",
        "wsgi.input": BytesIO(b""),
        "wsgi.errors": BytesIO(),
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
    }

    body = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], captured["headers"], body
