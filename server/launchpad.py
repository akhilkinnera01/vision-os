"""Launchpad view assembly for the local browser app shell."""

from __future__ import annotations

from server.store import SessionStore, ValidationStore, WorkspaceStore


PRIMARY_ACTIONS: tuple[dict[str, str], ...] = (
    {
        "title": "New Space",
        "description": "Create a reusable space with saved source, profile, and outputs.",
        "command": "python app.py --setup",
    },
    {
        "title": "Open Space",
        "description": "Jump back into a saved space and continue from its current configuration.",
        "command": "Open any workspace card below",
    },
    {
        "title": "Run Setup",
        "description": "Validate inputs, write starter files, and confirm Vision OS is ready to run.",
        "command": "python app.py --setup",
    },
    {
        "title": "Review Replay",
        "description": "Inspect a recent session or replay artifact without wiring the whole runtime by hand.",
        "command": "python app.py --source replay --input demo/demo-replay.jsonl",
    },
)

WORKSPACE_TABS: tuple[str, ...] = (
    "Live",
    "Zones",
    "Triggers",
    "Integrations",
    "History",
    "Settings",
)


class LaunchpadService:
    """Compose a browser-facing Launchpad snapshot from file-backed control-plane state."""

    def __init__(
        self,
        workspace_store: WorkspaceStore,
        session_store: SessionStore,
        validation_store: ValidationStore,
    ) -> None:
        self.workspace_store = workspace_store
        self.session_store = session_store
        self.validation_store = validation_store

    def build_snapshot(self) -> dict[str, object]:
        workspaces = self.workspace_store.list_workspaces()
        sessions = self.session_store.list_sessions()
        validations = self.validation_store.list_results()
        latest_sessions_by_workspace = {session.workspace_id: session for session in sessions}
        workspace_names = {workspace.workspace_id: workspace.name for workspace in workspaces}

        workspace_cards: list[dict[str, object]] = []
        for workspace in workspaces:
            validation = validations.get(workspace.workspace_id)
            latest_session = latest_sessions_by_workspace.get(workspace.workspace_id)
            workspace_cards.append(
                {
                    "workspace_id": workspace.workspace_id,
                    "name": workspace.name,
                    "source_mode": workspace.source_mode,
                    "profile_id": workspace.profile_id,
                    "validation_state": "unknown" if validation is None else validation.status,
                    "validation_summary": None if validation is None else validation.summary,
                    "last_run_state": "never_run" if latest_session is None else latest_session.state,
                    "href": f"/workspaces/{workspace.workspace_id}",
                }
            )

        recent_sessions = [
            {
                "session_id": session.session_id,
                "workspace_id": session.workspace_id,
                "workspace_name": workspace_names.get(session.workspace_id, session.workspace_id),
                "state": session.state,
                "started_at": session.started_at,
                "ended_at": session.ended_at,
                "href": f"/workspaces/{session.workspace_id}",
            }
            for session in sessions[:6]
        ]

        return {
            "title": "Vision OS Launchpad",
            "workspace_count": len(workspace_cards),
            "recent_session_count": len(recent_sessions),
            "primary_actions": list(PRIMARY_ACTIONS),
            "workspaces": workspace_cards,
            "recent_sessions": recent_sessions,
        }

    def build_workspace_surface(self, workspace_id: str) -> dict[str, object] | None:
        workspace = self.workspace_store.get_workspace(workspace_id)
        if workspace is None:
            return None

        validation = self.validation_store.get_result(workspace_id)
        latest_session = next(
            (session for session in self.session_store.list_sessions() if session.workspace_id == workspace_id),
            None,
        )
        return {
            "workspace": workspace.to_dict(),
            "status": {
                "validation_state": "unknown" if validation is None else validation.status,
                "validation_summary": None if validation is None else validation.summary,
                "last_run_state": "never_run" if latest_session is None else latest_session.state,
            },
            "tabs": list(WORKSPACE_TABS),
        }
