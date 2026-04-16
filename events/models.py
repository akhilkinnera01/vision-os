"""Typed event wrappers for scene and actor transitions."""

from __future__ import annotations

from dataclasses import dataclass

from common.models import VisionEvent


@dataclass(slots=True, frozen=True)
class SceneTransitionEvent(VisionEvent):
    category: str = "scene"


@dataclass(slots=True, frozen=True)
class DistractionEvent(VisionEvent):
    category: str = "distraction"


@dataclass(slots=True, frozen=True)
class CollaborationEvent(VisionEvent):
    category: str = "collaboration"


@dataclass(slots=True, frozen=True)
class StabilityEvent(VisionEvent):
    category: str = "stability"
