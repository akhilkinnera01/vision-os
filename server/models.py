"""Product-facing workspace and session models for the local web app."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class ArtifactIndex:
    """Paths to artifacts produced by a session."""

    replay_path: str | None = None
    history_path: str | None = None
    benchmark_path: str | None = None
    session_summary_path: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "replay_path": self.replay_path,
            "history_path": self.history_path,
            "benchmark_path": self.benchmark_path,
            "session_summary_path": self.session_summary_path,
        }


@dataclass(slots=True, frozen=True)
class WorkspaceManifest:
    """Saved space definition for the browser app and control plane."""

    workspace_id: str
    name: str
    source_mode: str
    profile_id: str | None = None
    policy_name: str | None = None
    source_ref: str | None = None
    zones_path: str | None = None
    triggers_path: str | None = None
    integrations_path: str | None = None
    outputs: ArtifactIndex = field(default_factory=ArtifactIndex)

    def to_dict(self) -> dict[str, object]:
        return {
            "workspace_id": self.workspace_id,
            "name": self.name,
            "source_mode": self.source_mode,
            "profile_id": self.profile_id,
            "policy_name": self.policy_name,
            "source_ref": self.source_ref,
            "zones_path": self.zones_path,
            "triggers_path": self.triggers_path,
            "integrations_path": self.integrations_path,
            "outputs": self.outputs.to_dict(),
        }


@dataclass(slots=True, frozen=True)
class WorkspaceSummary:
    """Launchpad card view of a saved space."""

    workspace_id: str
    name: str
    source_mode: str
    profile_id: str | None = None
    validation_state: str = "unknown"
    last_run_state: str = "never_run"

    def to_dict(self) -> dict[str, object]:
        return {
            "workspace_id": self.workspace_id,
            "name": self.name,
            "source_mode": self.source_mode,
            "profile_id": self.profile_id,
            "validation_state": self.validation_state,
            "last_run_state": self.last_run_state,
        }


@dataclass(slots=True, frozen=True)
class SessionRecord:
    """Metadata for one execution of a workspace."""

    session_id: str
    workspace_id: str
    state: str
    started_at: float | None = None
    ended_at: float | None = None
    artifacts: ArtifactIndex = field(default_factory=ArtifactIndex)

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "state": self.state,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "artifacts": self.artifacts.to_dict(),
        }


@dataclass(slots=True, frozen=True)
class SessionSnapshot:
    """Latest live state for the active session."""

    session_id: str
    workspace_id: str
    state: str
    scene_label: str | None = None
    explanation: str | None = None
    metrics: dict[str, object] = field(default_factory=dict)
    recent_events: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    active_zone_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "workspace_id": self.workspace_id,
            "state": self.state,
            "scene_label": self.scene_label,
            "explanation": self.explanation,
            "metrics": self.metrics,
            "recent_events": list(self.recent_events),
            "warnings": list(self.warnings),
            "active_zone_ids": list(self.active_zone_ids),
        }


@dataclass(slots=True, frozen=True)
class SessionEvent:
    """Append-only event emitted by the control plane."""

    session_id: str
    event_type: str
    timestamp: float
    payload: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }
