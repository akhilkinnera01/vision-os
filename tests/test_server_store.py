"""Tests for the browser-app workspace catalog."""

from __future__ import annotations

from pathlib import Path

from server.models import WorkspaceManifest
from server.store import WorkspaceStore


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
