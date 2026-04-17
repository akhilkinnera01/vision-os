"""Tests for browser-app workspace and session product models."""

from __future__ import annotations

from server.models import SessionRecord, SessionSnapshot, WorkspaceManifest


def test_workspace_manifest_round_trip_dict() -> None:
    manifest = WorkspaceManifest(
        workspace_id="desk-a",
        name="Desk A",
        source_mode="webcam",
        profile_id="workstation",
        zones_path="spaces/desk-a/zones.yaml",
        triggers_path="spaces/desk-a/triggers.yaml",
        integrations_path="spaces/desk-a/integrations.yaml",
    )

    payload = manifest.to_dict()

    assert payload["workspace_id"] == "desk-a"
    assert payload["name"] == "Desk A"
    assert payload["profile_id"] == "workstation"
    assert payload["integrations_path"] == "spaces/desk-a/integrations.yaml"


def test_session_record_tracks_workspace_run_state() -> None:
    record = SessionRecord(
        session_id="session-1",
        workspace_id="desk-a",
        state="running",
    )

    payload = record.to_dict()

    assert payload["session_id"] == "session-1"
    assert payload["workspace_id"] == "desk-a"
    assert payload["state"] == "running"


def test_session_snapshot_carries_live_operator_state() -> None:
    snapshot = SessionSnapshot(
        session_id="session-1",
        workspace_id="desk-a",
        state="running",
        scene_label="Focused Work",
        explanation="Desk appears occupied with sustained attention cues.",
        recent_events=("focus_started",),
    )

    payload = snapshot.to_dict()

    assert payload["state"] == "running"
    assert payload["scene_label"] == "Focused Work"
    assert payload["recent_events"] == ["focus_started"]
