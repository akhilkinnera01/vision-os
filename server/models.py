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

    @classmethod
    def from_dict(cls, payload: dict[str, object] | None) -> ArtifactIndex:
        if payload is None:
            return cls()
        return cls(
            replay_path=payload.get("replay_path"),
            history_path=payload.get("history_path"),
            benchmark_path=payload.get("benchmark_path"),
            session_summary_path=payload.get("session_summary_path"),
        )


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

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> WorkspaceManifest:
        return cls(
            workspace_id=str(payload["workspace_id"]),
            name=str(payload["name"]),
            source_mode=str(payload["source_mode"]),
            profile_id=_optional_str(payload.get("profile_id")),
            policy_name=_optional_str(payload.get("policy_name")),
            source_ref=_optional_str(payload.get("source_ref")),
            zones_path=_optional_str(payload.get("zones_path")),
            triggers_path=_optional_str(payload.get("triggers_path")),
            integrations_path=_optional_str(payload.get("integrations_path")),
            outputs=ArtifactIndex.from_dict(_optional_dict(payload.get("outputs"))),
        )


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

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> SessionRecord:
        return cls(
            session_id=str(payload["session_id"]),
            workspace_id=str(payload["workspace_id"]),
            state=str(payload["state"]),
            started_at=_optional_float(payload.get("started_at")),
            ended_at=_optional_float(payload.get("ended_at")),
            artifacts=ArtifactIndex.from_dict(_optional_dict(payload.get("artifacts"))),
        )


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

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> SessionSnapshot:
        return cls(
            session_id=str(payload["session_id"]),
            workspace_id=str(payload["workspace_id"]),
            state=str(payload["state"]),
            scene_label=_optional_str(payload.get("scene_label")),
            explanation=_optional_str(payload.get("explanation")),
            metrics=_optional_dict(payload.get("metrics")) or {},
            recent_events=tuple(str(item) for item in payload.get("recent_events", [])),
            warnings=tuple(str(item) for item in payload.get("warnings", [])),
            active_zone_ids=tuple(str(item) for item in payload.get("active_zone_ids", [])),
        )


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


@dataclass(slots=True, frozen=True)
class ValidationRecord:
    """Latest validation status known for a workspace."""

    workspace_id: str
    status: str
    checked_at: float
    summary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "workspace_id": self.workspace_id,
            "status": self.status,
            "checked_at": self.checked_at,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ValidationRecord:
        return cls(
            workspace_id=str(payload["workspace_id"]),
            status=str(payload["status"]),
            checked_at=float(payload["checked_at"]),
            summary=str(payload["summary"]),
        )


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_dict(value: object) -> dict[str, object] | None:
    return value if isinstance(value, dict) else None


def _optional_float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) else None
