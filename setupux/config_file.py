"""Load and save Easy Setup runtime config manifests."""

from __future__ import annotations

from pathlib import Path

import yaml

from common.config import VisionOSConfig
from common.models import OverlayMode, SourceMode
from setupux.models import SetupBundle


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


def write_runtime_config_file(config: VisionOSConfig, config_path: str) -> str:
    """Write a YAML runtime config manifest and keep bundle-local paths relative."""
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, object] = {
        "source": config.source_mode.value,
        "camera": config.camera_index,
        "model": config.model_name,
        "conf": config.confidence_threshold,
        "imgsz": config.image_size,
        "max_detections": config.max_detections,
        "profile": config.profile_name,
        "overlay_mode": config.overlay_mode.value,
        "temporal_window": config.temporal_window_seconds,
        "headless": config.headless,
        "log_json": config.log_json,
        "policy": config.policy_name,
    }
    if config.device is not None:
        payload["device"] = config.device
    if config.input_path is not None:
        payload["input"] = _relativize_path(path.parent, config.input_path)
    if config.profile_path is not None:
        payload["profile_file"] = _relativize_path(path.parent, config.profile_path)
    if config.zones_path is not None:
        payload["zones_file"] = _relativize_path(path.parent, config.zones_path)
    if config.trigger_path is not None:
        payload["trigger_file"] = _relativize_path(path.parent, config.trigger_path)
    if config.record_path is not None:
        payload["record"] = _relativize_path(path.parent, config.record_path)
    if config.benchmark_output_path is not None:
        payload["benchmark_output"] = _relativize_path(path.parent, config.benchmark_output_path)
    if config.history_output_path is not None:
        payload["history_output"] = _relativize_path(path.parent, config.history_output_path)
    if config.session_summary_output_path is not None:
        payload["session_summary_output"] = _relativize_path(path.parent, config.session_summary_output_path)
    if config.policy_path is not None:
        payload["policy_file"] = _relativize_path(path.parent, config.policy_path)
    if config.max_frames is not None:
        payload["max_frames"] = config.max_frames

    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False)
    return str(path)


def write_starter_bundle(
    *,
    output_dir: str,
    source_mode: SourceMode,
    camera_index: int,
    profile_name: str | None,
    overlay_mode: OverlayMode,
) -> SetupBundle:
    """Write a starter config plus stub zone/trigger files for later editing."""
    bundle_dir = Path(output_dir)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    zones_path = bundle_dir / "visionos.zones.yaml"
    zones_path.write_text(_starter_zones_template(), encoding="utf-8")

    trigger_path = bundle_dir / "visionos.triggers.yaml"
    trigger_path.write_text(_starter_triggers_template(), encoding="utf-8")

    config_path = bundle_dir / "visionos.config.yaml"
    write_runtime_config_file(
        VisionOSConfig(
            source_mode=source_mode,
            camera_index=camera_index,
            profile_name=profile_name,
            overlay_mode=overlay_mode,
        ),
        str(config_path),
    )

    return SetupBundle(
        config_path=str(config_path),
        zones_path=str(zones_path),
        trigger_path=str(trigger_path),
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


def _relativize_path(base_dir: Path, candidate: str) -> str:
    path = Path(candidate)
    resolved = path if path.is_absolute() else (base_dir / path).resolve()
    try:
        return str(resolved.relative_to(base_dir.resolve()))
    except ValueError:
        return str(resolved)


def _starter_zones_template() -> str:
    return (
        "# Starter zones file for Vision OS.\n"
        "# Add polygon zones here, then reference this file with --zones-file or\n"
        "# uncomment zones_file in visionos.config.yaml after the zones are ready.\n"
        "zones: []\n"
    )


def _starter_triggers_template() -> str:
    return (
        "# Starter triggers file for Vision OS.\n"
        "# Add trigger rules here, then reference this file with --trigger-file or\n"
        "# uncomment trigger_file in visionos.config.yaml after the rules are ready.\n"
        "triggers: []\n"
    )
