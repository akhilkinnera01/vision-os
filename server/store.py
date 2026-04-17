"""File-backed workspace catalog for the local browser app."""

from __future__ import annotations

import json
from pathlib import Path

from server.models import WorkspaceManifest


class WorkspaceStore:
    """Persist and list saved workspaces for the Launchpad."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def list_workspaces(self) -> tuple[WorkspaceManifest, ...]:
        if not self.path.is_file():
            return ()

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Workspace catalog must be a list: {self.path}")

        items: list[WorkspaceManifest] = []
        for raw_item in payload:
            if not isinstance(raw_item, dict):
                raise ValueError(f"Workspace catalog items must be mappings: {self.path}")
            items.append(WorkspaceManifest.from_dict(raw_item))
        return tuple(items)

    def save_workspace(self, manifest: WorkspaceManifest) -> None:
        existing = [item for item in self.list_workspaces() if item.workspace_id != manifest.workspace_id]
        payload = [item.to_dict() for item in existing]
        payload.append(manifest.to_dict())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
