"""File-backed workspace, session, and validation catalogs for the local browser app."""

from __future__ import annotations

import json
from pathlib import Path

from server.models import SessionRecord, ValidationRecord, WorkspaceManifest


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

    def get_workspace(self, workspace_id: str) -> WorkspaceManifest | None:
        for item in self.list_workspaces():
            if item.workspace_id == workspace_id:
                return item
        return None

    def save_workspace(self, manifest: WorkspaceManifest) -> None:
        existing = [item for item in self.list_workspaces() if item.workspace_id != manifest.workspace_id]
        payload = [item.to_dict() for item in existing]
        payload.append(manifest.to_dict())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class SessionStore:
    """Persist completed session records for Launchpad history cards."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def list_sessions(self, *, limit: int | None = None) -> tuple[SessionRecord, ...]:
        if not self.path.is_file():
            return ()

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError(f"Session catalog must be a list: {self.path}")

        items: list[SessionRecord] = []
        for raw_item in payload:
            if not isinstance(raw_item, dict):
                raise ValueError(f"Session catalog items must be mappings: {self.path}")
            items.append(SessionRecord.from_dict(raw_item))

        items.reverse()
        if limit is not None:
            items = items[:limit]
        return tuple(items)

    def append_session(self, record: SessionRecord) -> None:
        payload = [item.to_dict() for item in reversed(self.list_sessions())]
        payload.append(record.to_dict())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


class ValidationStore:
    """Persist the latest validation report summary for each workspace."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def list_results(self) -> dict[str, ValidationRecord]:
        if not self.path.is_file():
            return {}

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Validation catalog must be a mapping: {self.path}")

        items: dict[str, ValidationRecord] = {}
        for workspace_id, raw_item in payload.items():
            if not isinstance(raw_item, dict):
                raise ValueError(f"Validation catalog items must be mappings: {self.path}")
            items[workspace_id] = ValidationRecord.from_dict(raw_item)
        return items

    def get_result(self, workspace_id: str) -> ValidationRecord | None:
        return self.list_results().get(workspace_id)

    def save_result(self, record: ValidationRecord) -> None:
        payload = {workspace_id: item.to_dict() for workspace_id, item in self.list_results().items()}
        payload[record.workspace_id] = record.to_dict()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
