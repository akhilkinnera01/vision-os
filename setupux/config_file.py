"""Load and save Easy Setup runtime config manifests."""

from __future__ import annotations

from pathlib import Path

import yaml

from common.config import VisionOSConfig
from common.models import OverlayMode, SourceMode


class SetupConfigError(ValueError):
    """Raised when an Easy Setup config manifest is invalid."""


def load_runtime_config_file(config_path: str) -> VisionOSConfig:
    """Load a YAML runtime config manifest and resolve relative paths."""
    path = Path(config_path)
    if not path.is_file():
        raise SetupConfigError(f"Setup config not found: {path}")

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise SetupConfigError(f"Setup config root must be a mapping: {path}")

    base_dir = path.parent
    source_value = str(payload.get("source", SourceMode.WEBCAM.value))
    try:
        source_mode = SourceMode(source_value)
    except ValueError as exc:
        raise SetupConfigError(f"Setup config field 'source' is invalid: {source_value}") from exc

    overlay_value = str(payload.get("overlay_mode", OverlayMode.COMPACT.value))
    try:
        overlay_mode = OverlayMode(overlay_value)
    except ValueError as exc:
        raise SetupConfigError(f"Setup config field 'overlay_mode' is invalid: {overlay_value}") from exc

    policy_name = str(payload.get("policy", "default"))
    policy_path = _resolve_optional_path(base_dir, payload.get("policy_file"), must_exist=False)

    return VisionOSConfig(
        camera_index=int(payload.get("camera", 0)),
        model_name=str(payload.get("model", "yolov8n.pt")),
        confidence_threshold=float(payload.get("conf", 0.35)),
        image_size=int(payload.get("imgsz", 640)),
        device=None if payload.get("device") in (None, "") else str(payload.get("device")),
        max_detections=int(payload.get("max_detections", 25)),
        source_mode=source_mode,
        input_path=_resolve_optional_path(base_dir, payload.get("input"), must_exist=False),
        profile_name=None if payload.get("profile") in (None, "") else str(payload.get("profile")),
        profile_path=_resolve_optional_path(base_dir, payload.get("profile_file"), must_exist=False),
        zones_path=_resolve_optional_path(base_dir, payload.get("zones_file"), must_exist=False),
        trigger_path=_resolve_optional_path(base_dir, payload.get("trigger_file"), must_exist=False),
        record_path=_resolve_optional_path(base_dir, payload.get("record"), must_exist=False),
        benchmark_output_path=_resolve_optional_path(base_dir, payload.get("benchmark_output"), must_exist=False),
        history_output_path=_resolve_optional_path(base_dir, payload.get("history_output"), must_exist=False),
        session_summary_output_path=_resolve_optional_path(
            base_dir,
            payload.get("session_summary_output"),
            must_exist=False,
        ),
        policy_name=policy_name,
        policy_path=policy_path,
        overlay_mode=overlay_mode,
        temporal_window_seconds=float(payload.get("temporal_window", 8.0)),
        max_frames=None if payload.get("max_frames") in (None, "") else int(payload.get("max_frames")),
        headless=bool(payload.get("headless", False)),
        log_json=bool(payload.get("log_json", False)),
        config_path=str(path),
        policy_explicit=("policy" in payload) or ("policy_file" in payload),
        zones_explicit="zones_file" in payload,
        trigger_explicit="trigger_file" in payload,
        overlay_mode_explicit="overlay_mode" in payload,
    )


def _resolve_optional_path(base_dir: Path, value: object, *, must_exist: bool) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise SetupConfigError("Setup config path fields must be non-empty strings when present.")
    candidate = Path(value)
    resolved = candidate if candidate.is_absolute() else (base_dir / candidate).resolve()
    if must_exist and not resolved.exists():
        raise SetupConfigError(f"Setup config path does not exist: {value}")
    return str(resolved)
