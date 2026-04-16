"""Typed data models passed between the modular pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ContextLabel(StrEnum):
    """Stable scene labels used throughout the reasoning stack."""

    FOCUSED_WORK = "Focused Work"
    CASUAL_USE = "Casual Use"
    GROUP_ACTIVITY = "Group Activity"


class SourceMode(StrEnum):
    """Supported runtime input modes."""

    WEBCAM = "webcam"
    VIDEO = "video"
    REPLAY = "replay"


class OverlayMode(StrEnum):
    """UI density modes for the renderer."""

    COMPACT = "compact"
    DEBUG = "debug"


@dataclass(slots=True, frozen=True)
class BoundingBox:
    """Pixel coordinates for one detected object."""

    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return max(0, self.x2 - self.x1)

    @property
    def height(self) -> int:
        return max(0, self.y2 - self.y1)

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)

    def to_dict(self) -> dict[str, int]:
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

    @classmethod
    def from_dict(cls, payload: dict[str, int]) -> BoundingBox:
        return cls(
            x1=int(payload["x1"]),
            y1=int(payload["y1"]),
            x2=int(payload["x2"]),
            y2=int(payload["y2"]),
        )


@dataclass(slots=True, frozen=True)
class Detection:
    """Structured object returned by the perception layer."""

    label: str
    confidence: float
    bbox: BoundingBox
    area_ratio: float
    class_id: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "confidence": self.confidence,
            "bbox": self.bbox.to_dict(),
            "area_ratio": self.area_ratio,
            "class_id": self.class_id,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> Detection:
        return cls(
            label=str(payload["label"]),
            confidence=float(payload["confidence"]),
            bbox=BoundingBox.from_dict(dict(payload["bbox"])),
            area_ratio=float(payload["area_ratio"]),
            class_id=None if payload.get("class_id") is None else int(payload["class_id"]),
        )


@dataclass(slots=True, frozen=True)
class SceneFeatures:
    """Boolean and numeric scene features derived from detections."""

    counts: dict[str, int] = field(default_factory=dict)
    person_count: int = 0
    has_laptop: bool = False
    has_phone: bool = False
    has_book: bool = False
    has_keyboard: bool = False
    has_mouse: bool = False
    has_monitor: bool = False
    has_chair: bool = False
    workspace_score: float = 0.0
    collaboration_score: float = 0.0
    casual_score: float = 0.0
    occupied_ratio: float = 0.0
    dominant_label: str = "none"
    laptop_near_person: bool = False
    phone_near_person: bool = False
    multiple_people_clustered: bool = False
    centered_monitor: bool = False
    desk_like_score: float = 0.0
    room_like_score: float = 0.0
    person_laptop_distance: float = 1.0
    person_phone_distance: float = 1.0
    people_cluster_score: float = 0.0
    center_dominance_score: float = 0.0


@dataclass(slots=True, frozen=True)
class SceneMetrics:
    """Normalized live scores and temporal scene health indicators."""

    focus_score: float = 0.0
    distraction_score: float = 0.0
    collaboration_score: float = 0.0
    stability_score: float = 0.0
    focus_duration_seconds: float = 0.0
    decision_switch_rate: float = 0.0
    distraction_spike: bool = False
    collaboration_increasing: bool = False
    context_unstable: bool = False


@dataclass(slots=True, frozen=True)
class RuntimeMetrics:
    """Runtime and benchmark counters accumulated during execution."""

    frames_processed: int = 0
    fps: float = 0.0
    average_inference_ms: float = 0.0
    dropped_frames: int = 0

    def to_dict(self) -> dict[str, float | int]:
        return {
            "frames_processed": self.frames_processed,
            "fps": self.fps,
            "average_inference_ms": self.average_inference_ms,
            "dropped_frames": self.dropped_frames,
        }


@dataclass(slots=True, frozen=True)
class TemporalSnapshot:
    """One timestamped memory sample stored in the rolling state window."""

    timestamp: float
    label: ContextLabel
    confidence: float
    features: SceneFeatures


@dataclass(slots=True, frozen=True)
class TemporalState:
    """Aggregated temporal state derived from the sliding window."""

    window_span_seconds: float = 0.0
    dominant_label: ContextLabel | None = None
    dominant_duration_seconds: float = 0.0
    label_switch_count: int = 0
    notes: list[str] = field(default_factory=list)
    metrics: SceneMetrics = field(default_factory=SceneMetrics)


@dataclass(slots=True, frozen=True)
class SceneContext:
    """High-level context inferred from the feature set."""

    label: ContextLabel
    confidence: float
    signals: list[str] = field(default_factory=list)
    confidence_reason: str = ""


@dataclass(slots=True, frozen=True)
class Decision:
    """Final classification plus a downstream action suggestion."""

    label: ContextLabel
    confidence: float
    action: str
    reasoning_facts: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    scene_metrics: SceneMetrics = field(default_factory=SceneMetrics)


@dataclass(slots=True, frozen=True)
class Explanation:
    """Structured explanation payload for compact and debug rendering."""

    scene_label: str
    top_signals: list[str]
    risk_flags: list[str]
    action: str
    confidence_reason: str
    compact_summary: str
    debug_lines: list[str]
    scores: dict[str, float]


@dataclass(slots=True, frozen=True)
class ReplayRecord:
    """Machine-readable replay artifact for deterministic debugging."""

    frame_index: int
    timestamp: float
    frame_shape: tuple[int, int]
    detections: list[Detection]
    source_mode: SourceMode

    def to_dict(self) -> dict[str, object]:
        return {
            "frame_index": self.frame_index,
            "timestamp": self.timestamp,
            "frame_shape": list(self.frame_shape),
            "detections": [detection.to_dict() for detection in self.detections],
            "source_mode": self.source_mode.value,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> ReplayRecord:
        return cls(
            frame_index=int(payload["frame_index"]),
            timestamp=float(payload["timestamp"]),
            frame_shape=tuple(int(value) for value in payload["frame_shape"]),
            detections=[Detection.from_dict(item) for item in payload["detections"]],
            source_mode=SourceMode(str(payload["source_mode"])),
        )
