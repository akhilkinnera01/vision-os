"""Typed data models passed between the modular pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ContextLabel(StrEnum):
    """Stable scene labels used throughout the reasoning stack."""

    FOCUSED_WORK = "Focused Work"
    CASUAL_USE = "Casual Use"
    GROUP_ACTIVITY = "Group Activity"


@dataclass(slots=True, frozen=True)
class BoundingBox:
    """Pixel coordinates for one detected object."""

    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(slots=True, frozen=True)
class Detection:
    """Structured object returned by the perception layer."""

    label: str
    confidence: float
    bbox: BoundingBox
    area_ratio: float
    class_id: int | None = None


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


@dataclass(slots=True, frozen=True)
class SceneContext:
    """High-level context inferred from the feature set."""

    label: ContextLabel
    confidence: float
    signals: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class Decision:
    """Final classification plus a downstream action suggestion."""

    label: ContextLabel
    confidence: float
    action: str
    reasoning_facts: list[str] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class Explanation:
    """Presentation-friendly explanation payload for the UI layer."""

    summary: str
