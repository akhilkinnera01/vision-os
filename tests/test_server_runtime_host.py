"""Tests for the runtime-host seam used by the local browser app."""

from __future__ import annotations

from server.runtime_host import RuntimeHost


def test_runtime_host_tracks_running_state() -> None:
    host = RuntimeHost()

    host.start()
    assert host.is_running is True

    host.stop()
    assert host.is_running is False


def test_runtime_host_records_the_active_workspace_id() -> None:
    host = RuntimeHost()

    host.start(workspace_id="desk-a")

    assert host.active_workspace_id == "desk-a"
