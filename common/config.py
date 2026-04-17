"""Runtime configuration shared across the application."""

from __future__ import annotations

from dataclasses import dataclass

from common.models import OverlayMode, SourceMode


@dataclass(slots=True)
class VisionOSConfig:
    """Small config object that keeps the app wiring explicit and testable."""

    camera_index: int = 0
    model_name: str = "yolov8n.pt"
    confidence_threshold: float = 0.35
    image_size: int = 640
    device: str | None = None
    max_detections: int = 25
    source_mode: SourceMode = SourceMode.WEBCAM
    input_path: str | None = None
    zones_path: str | None = None
    record_path: str | None = None
    benchmark_output_path: str | None = None
    policy_name: str = "default"
    policy_path: str | None = None
    overlay_mode: OverlayMode = OverlayMode.COMPACT
    temporal_window_seconds: float = 8.0
    max_frames: int | None = None
    headless: bool = False
    log_json: bool = False
