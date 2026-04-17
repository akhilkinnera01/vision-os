"""Typed zone definitions for zone-aware spatial reasoning."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum

from common.models import Detection, SceneFeatures


class ZoneType(StrEnum):
    """Supported V1 zone categories."""

    OCCUPANCY = "occupancy"
    ACTIVITY = "activity"
    TRANSITION = "transition"


class ZoneContextLabel(StrEnum):
    """Stable zone-local labels."""

    EMPTY = "empty"
    OCCUPIED = "occupied"
    SOLO_FOCUS = "solo_focus"
    GROUP_ACTIVITY = "group_activity"
    CASUAL_OCCUPANCY = "casual_occupancy"


@dataclass(slots=True, frozen=True)
class ZonePoint:
    """One polygon vertex in image pixel space."""

    x: float
    y: float

    def to_list(self) -> list[float]:
        return [self.x, self.y]


@dataclass(slots=True, frozen=True)
class Zone:
    """One user-defined named region within the camera frame."""

    zone_id: str
    name: str
    zone_type: ZoneType
    polygon: tuple[ZonePoint, ...]
    enabled: bool = True
    labels_of_interest: tuple[str, ...] = field(default_factory=tuple)
    profile: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.zone_id,
            "name": self.name,
            "type": self.zone_type.value,
            "polygon": [point.to_list() for point in self.polygon],
            "enabled": self.enabled,
        }
        if self.labels_of_interest:
            payload["labels_of_interest"] = list(self.labels_of_interest)
        if self.profile is not None:
            payload["profile"] = self.profile
        return payload


@dataclass(slots=True, frozen=True)
class ZoneAssignment:
    """Primary zone membership for one detection in the current frame."""

    zone_id: str
    detection: Detection
    method: str
    score: float


@dataclass(slots=True, frozen=True)
class ZoneFeatureSet:
    """Zone-local feature bundle derived from assigned detections and actors."""

    zone_id: str
    zone_name: str
    zone_type: ZoneType
    features: SceneFeatures = field(default_factory=SceneFeatures)
    detection_count: int = 0
    occupied: bool = False
    actor_track_ids: tuple[int, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "zone_type": self.zone_type.value,
            "features": asdict(self.features),
            "detection_count": self.detection_count,
            "occupied": self.occupied,
            "actor_track_ids": list(self.actor_track_ids),
        }


@dataclass(slots=True, frozen=True)
class ZoneContext:
    """High-level zone-local interpretation."""

    label: ZoneContextLabel
    confidence: float
    signals: tuple[str, ...] = field(default_factory=tuple)
    confidence_reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label.value,
            "confidence": self.confidence,
            "signals": list(self.signals),
            "confidence_reason": self.confidence_reason,
        }


@dataclass(slots=True, frozen=True)
class ZoneDecision:
    """Final zone-local action suggestion."""

    label: ZoneContextLabel
    confidence: float
    action: str
    reasoning_facts: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label.value,
            "confidence": self.confidence,
            "action": self.action,
            "reasoning_facts": list(self.reasoning_facts),
        }


@dataclass(slots=True, frozen=True)
class ZoneTemporalSnapshot:
    """One zone-local time sample within the rolling memory window."""

    timestamp: float
    label: ZoneContextLabel
    occupied: bool


@dataclass(slots=True, frozen=True)
class ZoneTemporalState:
    """Aggregated temporal state for one zone."""

    window_span_seconds: float = 0.0
    dominant_label: ZoneContextLabel | None = None
    current_label_duration_seconds: float = 0.0
    occupied_duration_seconds: float = 0.0
    label_switch_count: int = 0
    stability_score: float = 0.0
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "window_span_seconds": self.window_span_seconds,
            "dominant_label": None if self.dominant_label is None else self.dominant_label.value,
            "current_label_duration_seconds": self.current_label_duration_seconds,
            "occupied_duration_seconds": self.occupied_duration_seconds,
            "label_switch_count": self.label_switch_count,
            "stability_score": self.stability_score,
            "notes": list(self.notes),
        }


@dataclass(slots=True, frozen=True)
class ZoneRuntimeState:
    """Current end-to-end zone-local runtime output."""

    zone_id: str
    zone_name: str
    zone_type: ZoneType
    feature_set: ZoneFeatureSet
    context: ZoneContext
    decision: ZoneDecision
    temporal_state: ZoneTemporalState

    def to_dict(self) -> dict[str, object]:
        return {
            "zone_id": self.zone_id,
            "zone_name": self.zone_name,
            "zone_type": self.zone_type.value,
            "feature_set": self.feature_set.to_dict(),
            "context": self.context.to_dict(),
            "decision": self.decision.to_dict(),
            "temporal_state": self.temporal_state.to_dict(),
        }
