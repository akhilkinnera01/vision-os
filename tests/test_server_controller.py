"""Tests for one-active-session lifecycle control."""

from __future__ import annotations

from server.controller import SessionController
from server.models import WorkspaceManifest


def test_session_controller_allows_only_one_active_session() -> None:
    controller = SessionController()
    desk = WorkspaceManifest(workspace_id="desk-a", name="Desk A", source_mode="webcam")
    room = WorkspaceManifest(workspace_id="room-a", name="Room A", source_mode="video")

    first = controller.start_session(desk)

    try:
        controller.start_session(room)
    except RuntimeError as exc:
        assert "active session" in str(exc)
    else:  # pragma: no cover - explicit failure path for readability
        raise AssertionError("expected one-active-session guard")

    assert first.workspace_id == "desk-a"
    assert controller.active_session is first


def test_session_controller_finishes_the_active_session() -> None:
    controller = SessionController()
    desk = WorkspaceManifest(workspace_id="desk-a", name="Desk A", source_mode="webcam")

    running = controller.start_session(desk)
    completed = controller.finish_session("completed")

    assert running.state == "running"
    assert completed.workspace_id == "desk-a"
    assert completed.state == "completed"
    assert completed.ended_at is not None
    assert controller.active_session is None
