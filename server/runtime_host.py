"""Runtime host for browser-controlled local Vision OS sessions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

from server.models import WorkspaceManifest


@dataclass(slots=True)
class RuntimeHost:
    """Launch and stop one active Vision OS runtime process for the browser shell."""

    app_path: Path
    python_executable: str = sys.executable
    _process: subprocess.Popen | None = None
    _active_workspace_id: str | None = None
    _active_record_path: str | None = None
    _launch_counter: int = 0

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    @property
    def active_workspace_id(self) -> str | None:
        if not self.is_running:
            return None
        return self._active_workspace_id

    @property
    def active_record_path(self) -> str | None:
        if not self.is_running:
            return None
        return self._active_record_path

    def start(self, *, workspace: WorkspaceManifest, record_replay: bool = False) -> str | None:
        if self.is_running:
            raise RuntimeError("Cannot start a new session while another active session is running.")
        if record_replay and workspace.source_mode == "replay":
            raise RuntimeError("Replay sources already have recorded input; browser recording is only available for live or video runs.")

        command, record_path = self._build_command(workspace, record_replay=record_replay)
        self._process = subprocess.Popen(command, cwd=str(self.app_path.parent))
        self._active_workspace_id = workspace.workspace_id
        self._active_record_path = record_path
        return record_path

    def stop(self) -> None:
        if self._process is None:
            self._active_workspace_id = None
            self._active_record_path = None
            return

        if self._process.poll() is None:
            self._process.terminate()
            self._process.wait(timeout=2.0)
        self._process = None
        self._active_workspace_id = None
        self._active_record_path = None

    def _build_command(self, workspace: WorkspaceManifest, *, record_replay: bool = False) -> tuple[list[str], str | None]:
        command = [self.python_executable, str(self.app_path), "--headless"]
        record_path = self._resolve_record_path(workspace, record_replay=record_replay)
        if workspace.config_path:
            command.extend(["--config", workspace.config_path])
            self._append_workspace_overrides(command, workspace, record_path=record_path)
            return command, record_path

        command.extend(["--source", workspace.source_mode])
        if workspace.source_mode == "webcam":
            command.extend(["--camera", workspace.source_ref or "0"])
        elif workspace.source_ref is not None:
            command.extend(["--input", workspace.source_ref])

        if workspace.profile_id:
            command.extend(["--profile", workspace.profile_id])
        if workspace.profile_path:
            command.extend(["--profile-file", workspace.profile_path])
        if workspace.policy_path:
            command.extend(["--policy-file", workspace.policy_path])
        elif workspace.policy_name:
            command.extend(["--policy", workspace.policy_name])
        if workspace.zones_path:
            command.extend(["--zones-file", workspace.zones_path])
        if workspace.triggers_path:
            command.extend(["--trigger-file", workspace.triggers_path])
        if workspace.integrations_path:
            command.extend(["--integrations-file", workspace.integrations_path])
        if record_path is not None:
            command.extend(["--record", record_path])
        if workspace.outputs.history_path:
            command.extend(["--history-output", workspace.outputs.history_path])
        if workspace.outputs.benchmark_path:
            command.extend(["--benchmark-output", workspace.outputs.benchmark_path])
        if workspace.outputs.session_summary_path:
            command.extend(["--session-summary-output", workspace.outputs.session_summary_path])
        return command, record_path

    def _append_workspace_overrides(
        self,
        command: list[str],
        workspace: WorkspaceManifest,
        *,
        record_path: str | None,
    ) -> None:
        command.extend(["--source", workspace.source_mode])
        if workspace.source_mode == "webcam":
            command.extend(["--camera", workspace.source_ref or "0"])
        elif workspace.source_ref is not None:
            command.extend(["--input", workspace.source_ref])

        if workspace.profile_id:
            command.extend(["--profile", workspace.profile_id])
        if workspace.profile_path:
            command.extend(["--profile-file", workspace.profile_path])
        if workspace.policy_path:
            command.extend(["--policy-file", workspace.policy_path])
        elif workspace.policy_name:
            command.extend(["--policy", workspace.policy_name])
        if workspace.zones_path:
            command.extend(["--zones-file", workspace.zones_path])
        if workspace.triggers_path:
            command.extend(["--trigger-file", workspace.triggers_path])
        if workspace.integrations_path:
            command.extend(["--integrations-file", workspace.integrations_path])
        if record_path is not None:
            command.extend(["--record", record_path])
        if workspace.outputs.history_path:
            command.extend(["--history-output", workspace.outputs.history_path])
        if workspace.outputs.benchmark_path:
            command.extend(["--benchmark-output", workspace.outputs.benchmark_path])
        if workspace.outputs.session_summary_path:
            command.extend(["--session-summary-output", workspace.outputs.session_summary_path])

    def _resolve_record_path(self, workspace: WorkspaceManifest, *, record_replay: bool) -> str | None:
        if not record_replay:
            return workspace.outputs.replay_path
        if workspace.outputs.replay_path is not None:
            return workspace.outputs.replay_path
        self._launch_counter += 1
        return str(self.app_path.parent / ".visionos" / "artifacts" / f"{workspace.workspace_id}-recording-{self._launch_counter}.jsonl")
