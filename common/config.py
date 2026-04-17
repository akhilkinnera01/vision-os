"""Runtime configuration shared across the application."""

from __future__ import annotations

from dataclasses import dataclass

from common.models import OverlayMode, SourceMode


@dataclass(slots=True)
class VisionOSConfig:
    """Small config object that keeps the app wiring explicit and testable."""

    config_path: str | None = None
    app_mode: bool = False
    app_host: str = "127.0.0.1"
    app_port: int = 8765
    open_browser: bool = True
    setup_mode: bool = False
    list_cameras: bool = False
    validate_config: bool = False
    demo_mode: bool = False
    camera_index: int = 0
    model_name: str = "yolov8n.pt"
    confidence_threshold: float = 0.35
    image_size: int = 640
    device: str | None = None
    max_detections: int = 25
    source_mode: SourceMode = SourceMode.WEBCAM
    input_path: str | None = None
    profile_name: str | None = None
    profile_path: str | None = None
    zones_path: str | None = None
    trigger_path: str | None = None
    integrations_path: str | None = None
    record_path: str | None = None
    benchmark_output_path: str | None = None
    history_output_path: str | None = None
    session_summary_output_path: str | None = None
    policy_name: str = "default"
    policy_path: str | None = None
    overlay_mode: OverlayMode = OverlayMode.COMPACT
    temporal_window_seconds: float = 8.0
    max_frames: int | None = None
    headless: bool = False
    log_json: bool = False
    policy_explicit: bool = False
    zones_explicit: bool = False
    trigger_explicit: bool = False
    integrations_explicit: bool = False
    overlay_mode_explicit: bool = False
