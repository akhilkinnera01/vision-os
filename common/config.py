"""Runtime configuration shared across the application."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class VisionOSConfig:
    """Small config object that keeps the app wiring explicit and testable."""

    camera_index: int = 0
    model_name: str = "yolov8n.pt"
    confidence_threshold: float = 0.35
    image_size: int = 640
    device: str | None = None
    max_detections: int = 25

