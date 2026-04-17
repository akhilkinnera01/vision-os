"""Session lifecycle control for the local browser app."""

from __future__ import annotations

from dataclasses import replace
import time

from server.models import SessionRecord, WorkspaceManifest


class SessionController:
    """Own one-active-session lifecycle state for the local control plane."""

    def __init__(self) -> None:
        self._active_session: SessionRecord | None = None
        self._session_counter = 0

    @property
    def active_session(self) -> SessionRecord | None:
        return self._active_session

    def start_session(self, workspace: WorkspaceManifest) -> SessionRecord:
        if self._active_session is not None and self._active_session.state == "running":
            raise RuntimeError("Cannot start a new session while another active session is running.")

        self._session_counter += 1
        self._active_session = SessionRecord(
            session_id=f"session-{self._session_counter}",
            workspace_id=workspace.workspace_id,
            state="running",
            started_at=time.time(),
            artifacts=workspace.outputs,
        )
        return self._active_session

    def finish_session(self, final_state: str) -> SessionRecord:
        if self._active_session is None:
            raise RuntimeError("Cannot finish a session when no active session exists.")

        completed = replace(
            self._active_session,
            state=final_state,
            ended_at=time.time(),
        )
        self._active_session = None
        return completed
