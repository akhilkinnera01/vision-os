"""Runtime host seam for the local Vision OS control plane."""

from __future__ import annotations


class RuntimeHost:
    """Track runtime ownership before the worker implementation lands."""

    def __init__(self) -> None:
        self.is_running = False
        self.active_workspace_id: str | None = None

    def start(self, *, workspace_id: str | None = None) -> None:
        self.is_running = True
        self.active_workspace_id = workspace_id

    def stop(self) -> None:
        self.is_running = False
        self.active_workspace_id = None
