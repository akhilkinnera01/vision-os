"""Tests for the browser-app workspace, session, and validation catalogs."""

from __future__ import annotations

from pathlib import Path

from server.models import SessionRecord, ValidationRecord, WorkspaceManifest
from server.store import SessionStore, ValidationStore, WorkspaceStore


def test_workspace_store_returns_empty_list_when_catalog_missing(tmp_path: Path) -> None:
    store = WorkspaceStore(tmp_path / "catalog.json")

    assert store.list_workspaces() == ()


def test_workspace_store_persists_and_lists_workspaces(tmp_path: Path) -> None:
    store = WorkspaceStore(tmp_path / "catalog.json")
    manifest = WorkspaceManifest(
        workspace_id="desk-a",
        name="Desk A",
        source_mode="webcam",
    )

    store.save_workspace(manifest)

    items = store.list_workspaces()
    assert len(items) == 1
    assert items[0].workspace_id == "desk-a"
    assert items[0].name == "Desk A"


def test_workspace_store_replaces_existing_workspace_by_id(tmp_path: Path) -> None:
    store = WorkspaceStore(tmp_path / "catalog.json")
    store.save_workspace(WorkspaceManifest(workspace_id="desk-a", name="Desk A", source_mode="webcam"))

    store.save_workspace(WorkspaceManifest(workspace_id="desk-a", name="Desk Alpha", source_mode="video"))

    items = store.list_workspaces()
    assert len(items) == 1
    assert items[0].name == "Desk Alpha"
    assert items[0].source_mode == "video"


def test_session_store_returns_recent_sessions_newest_first(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.json")
    older = SessionRecord(session_id="session-1", workspace_id="desk-a", state="completed", started_at=10.0)
    newer = SessionRecord(session_id="session-2", workspace_id="room-a", state="failed", started_at=20.0)

    store.append_session(older)
    store.append_session(newer)

    items = store.list_sessions()
    assert [item.session_id for item in items] == ["session-2", "session-1"]


def test_validation_store_overwrites_by_workspace_id(tmp_path: Path) -> None:
    store = ValidationStore(tmp_path / "validations.json")

    store.save_result(
        ValidationRecord(
            workspace_id="desk-a",
            status="ok",
            checked_at=10.0,
            summary="Ready",
        )
    )
    store.save_result(
        ValidationRecord(
            workspace_id="desk-a",
            status="error",
            checked_at=20.0,
            summary="Camera missing",
        )
    )

    result = store.get_result("desk-a")
    assert result is not None
    assert result.status == "error"
    assert result.summary == "Camera missing"
