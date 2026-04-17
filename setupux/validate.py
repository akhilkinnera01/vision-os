"""Source discovery and setup validation helpers."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import cv2

from common.config import VisionOSConfig
from common.models import SourceMode
from common.policy import load_policy
from common.profile import RuntimeProfile, load_profile
from integrations import load_integration_config, load_trigger_config
from perception.detector import YOLODetector
from runtime.io import ReplayFrameSource, VideoFrameSource, WebcamFrameSource
from setupux.models import ValidationCheck, ValidationReport, ValidationStatus
from zones import load_zones


def discover_camera_indexes(max_index: int = 5) -> list[int]:
    """Return camera indexes that OpenCV can currently open."""
    available: list[int] = []
    for index in range(max_index):
        capture = cv2.VideoCapture(index)
        try:
            if capture.isOpened():
                available.append(index)
        finally:
            capture.release()
    return available


def validate_runtime_setup(config: VisionOSConfig, *, include_model_check: bool = True) -> ValidationReport:
    """Run a lightweight setup validation pass without entering the main runtime."""
    effective_config, profile_check = _resolve_effective_validation_config(config)
    source_detail, source_status = _probe_source(config)
    checks = [
        profile_check,
        _check_policy(effective_config),
        _check_zones(effective_config),
        _check_triggers(effective_config),
        _check_integrations(effective_config),
        ValidationCheck(name="source", status=source_status, detail=source_detail),
        _check_output_paths(effective_config),
    ]
    if include_model_check:
        checks.append(_check_model(effective_config))
    else:
        checks.append(ValidationCheck(name="model", status=ValidationStatus.SKIPPED, detail="Model check skipped"))
    return ValidationReport(checks=tuple(checks))


def _probe_source(config: VisionOSConfig) -> tuple[str, ValidationStatus]:
    source = _build_probe_source(config)
    try:
        if not source.is_opened():
            return (f"Unable to open {config.source_mode.value} source", ValidationStatus.ERROR)
        packet = source.read()
        if packet is None:
            return (f"No frames available from {config.source_mode.value} source", ValidationStatus.ERROR)
        return (f"Read 1 frame from {config.source_mode.value} input", ValidationStatus.OK)
    finally:
        source.close()


def _build_probe_source(config: VisionOSConfig):
    if config.source_mode == SourceMode.WEBCAM:
        return WebcamFrameSource(config.camera_index)
    if config.source_mode == SourceMode.VIDEO:
        return VideoFrameSource(config.input_path or "")
    return ReplayFrameSource(config.input_path or "")


def _check_output_paths(config: VisionOSConfig) -> ValidationCheck:
    output_paths = [
        config.record_path,
        config.benchmark_output_path,
        config.history_output_path,
        config.session_summary_output_path,
    ]
    parents = {Path(path).parent for path in output_paths if path}
    for parent in parents:
        parent.mkdir(parents=True, exist_ok=True)
        if not parent.is_dir():
            return ValidationCheck(name="outputs", status=ValidationStatus.ERROR, detail=f"Unable to use {parent}")
    if not parents:
        return ValidationCheck(name="outputs", status=ValidationStatus.SKIPPED, detail="No output paths configured")
    return ValidationCheck(name="outputs", status=ValidationStatus.OK, detail=f"Validated {len(parents)} output directories")


def _check_model(config: VisionOSConfig) -> ValidationCheck:
    try:
        YOLODetector(config)
    except Exception as exc:  # pragma: no cover - environment-specific runtime failure
        return ValidationCheck(name="model", status=ValidationStatus.ERROR, detail=str(exc))
    return ValidationCheck(name="model", status=ValidationStatus.OK, detail=f"Loaded model {config.model_name}")


def _resolve_effective_validation_config(config: VisionOSConfig) -> tuple[VisionOSConfig, ValidationCheck]:
    if config.profile_name is None and config.profile_path is None:
        return (
            config,
            ValidationCheck(name="profile", status=ValidationStatus.SKIPPED, detail="No profile selected"),
        )

    try:
        profile = load_profile(name=config.profile_name, path=config.profile_path)
    except Exception as exc:
        return (
            config,
            ValidationCheck(name="profile", status=ValidationStatus.ERROR, detail=str(exc)),
        )
    return (_apply_profile_defaults_for_validation(config, profile), ValidationCheck(
        name="profile",
        status=ValidationStatus.OK,
        detail=f"Loaded profile {profile.profile_id}",
    ))


def _apply_profile_defaults_for_validation(config: VisionOSConfig, profile: RuntimeProfile) -> VisionOSConfig:
    resolved = config
    if not resolved.policy_explicit:
        if profile.policy_path is not None:
            resolved = replace(resolved, policy_path=profile.policy_path)
        else:
            resolved = replace(resolved, policy_name=profile.policy_name)
    if not resolved.zones_explicit and profile.zones_path is not None:
        resolved = replace(resolved, zones_path=profile.zones_path)
    if not resolved.trigger_explicit and profile.trigger_path is not None:
        resolved = replace(resolved, trigger_path=profile.trigger_path)
    if not resolved.integrations_explicit and profile.integrations_path is not None:
        resolved = replace(resolved, integrations_path=profile.integrations_path)
    return resolved


def _check_policy(config: VisionOSConfig) -> ValidationCheck:
    try:
        policy = load_policy(name=config.policy_name, path=config.policy_path)
    except Exception as exc:
        return ValidationCheck(name="policy", status=ValidationStatus.ERROR, detail=str(exc))
    return ValidationCheck(name="policy", status=ValidationStatus.OK, detail=f"Loaded policy {policy.name}")


def _check_zones(config: VisionOSConfig) -> ValidationCheck:
    if not config.zones_path:
        return ValidationCheck(name="zones", status=ValidationStatus.SKIPPED, detail="No zones file configured")
    try:
        zones = load_zones(config.zones_path)
    except Exception as exc:
        return ValidationCheck(name="zones", status=ValidationStatus.ERROR, detail=str(exc))
    return ValidationCheck(name="zones", status=ValidationStatus.OK, detail=f"Loaded {len(zones)} zones")


def _check_triggers(config: VisionOSConfig) -> ValidationCheck:
    if not config.trigger_path:
        return ValidationCheck(name="triggers", status=ValidationStatus.SKIPPED, detail="No trigger file configured")
    try:
        trigger_config = load_trigger_config(config.trigger_path)
    except Exception as exc:
        return ValidationCheck(name="triggers", status=ValidationStatus.ERROR, detail=str(exc))
    return ValidationCheck(
        name="triggers",
        status=ValidationStatus.OK,
        detail=f"Loaded {len(trigger_config.rules)} trigger rules",
    )


def _check_integrations(config: VisionOSConfig) -> ValidationCheck:
    if not config.integrations_path:
        return ValidationCheck(name="integrations", status=ValidationStatus.SKIPPED, detail="No integrations file configured")
    try:
        integration_config = load_integration_config(config.integrations_path)
    except Exception as exc:
        return ValidationCheck(name="integrations", status=ValidationStatus.ERROR, detail=str(exc))
    return ValidationCheck(
        name="integrations",
        status=ValidationStatus.OK,
        detail=f"Loaded {len(integration_config.targets)} integration targets",
    )
