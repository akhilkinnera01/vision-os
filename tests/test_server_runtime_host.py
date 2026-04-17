"""Tests for the runtime host used by the local browser app."""

from __future__ import annotations

from pathlib import Path

from server.models import ArtifactIndex, WorkspaceManifest
from server.runtime_host import RuntimeHost


class _FakeProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.wait_calls: list[float | None] = []
        self._returncode = None

    def poll(self):
        return self._returncode

    def terminate(self) -> None:
        self.terminated = True
        self._returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        self.wait_calls.append(timeout)
        self._returncode = 0
        return 0


def test_runtime_host_starts_a_subprocess_for_a_workspace(monkeypatch) -> None:
    captured = {}
    fake_process = _FakeProcess()

    monkeypatch.setattr(
        "server.runtime_host.subprocess.Popen",
        lambda command, cwd=None: captured.update({"command": command, "cwd": cwd}) or fake_process,
    )
    host = RuntimeHost(app_path=Path("/repo/vision-os/app.py"), python_executable="python-test")
    workspace = WorkspaceManifest(
        workspace_id="meeting-room-video",
        name="Meeting Room",
        source_mode="video",
        source_ref="demo/sample.mp4",
        profile_id="meeting_room",
        policy_name="default",
        zones_path="demo/sample-zones.yaml",
        triggers_path="demo/sample-triggers.yaml",
        integrations_path="demo/sample-integrations.yaml",
        outputs=ArtifactIndex(
            replay_path="out/session.jsonl",
            history_path="out/history.jsonl",
            benchmark_path="out/benchmark.json",
            session_summary_path="out/session-summary.json",
        ),
    )

    host.start(workspace=workspace)

    assert host.is_running is True
    assert host.active_workspace_id == "meeting-room-video"
    assert captured["cwd"] == "/repo/vision-os"
    assert captured["command"] == [
        "python-test",
        "/repo/vision-os/app.py",
        "--headless",
        "--source",
        "video",
        "--input",
        "demo/sample.mp4",
        "--profile",
        "meeting_room",
        "--policy",
        "default",
        "--zones-file",
        "demo/sample-zones.yaml",
        "--trigger-file",
        "demo/sample-triggers.yaml",
        "--integrations-file",
        "demo/sample-integrations.yaml",
        "--record",
        "out/session.jsonl",
        "--history-output",
        "out/history.jsonl",
        "--benchmark-output",
        "out/benchmark.json",
        "--session-summary-output",
        "out/session-summary.json",
    ]


def test_runtime_host_uses_saved_config_when_available(monkeypatch) -> None:
    captured = {}
    fake_process = _FakeProcess()
    monkeypatch.setattr(
        "server.runtime_host.subprocess.Popen",
        lambda command, cwd=None: captured.update({"command": command, "cwd": cwd}) or fake_process,
    )
    host = RuntimeHost(app_path=Path("/repo/vision-os/app.py"), python_executable="python-test")
    workspace = WorkspaceManifest(
        workspace_id="desk-a",
        name="Desk A",
        source_mode="webcam",
        config_path="visionos.config.yaml",
    )

    host.start(workspace=workspace)

    assert captured["command"] == [
        "python-test",
        "/repo/vision-os/app.py",
        "--headless",
        "--config",
        "visionos.config.yaml",
    ]


def test_runtime_host_stops_and_clears_the_active_workspace(monkeypatch) -> None:
    fake_process = _FakeProcess()
    monkeypatch.setattr("server.runtime_host.subprocess.Popen", lambda *args, **kwargs: fake_process)
    host = RuntimeHost(app_path=Path("/repo/vision-os/app.py"), python_executable="python-test")
    workspace = WorkspaceManifest(workspace_id="desk-a", name="Desk A", source_mode="webcam", source_ref="0")

    host.start(workspace=workspace)
    host.stop()

    assert fake_process.terminated is True
    assert fake_process.wait_calls == [2.0]
    assert host.is_running is False
    assert host.active_workspace_id is None
