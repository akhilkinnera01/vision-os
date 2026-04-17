"""Source discovery and setup validation helpers."""

from __future__ import annotations

from pathlib import Path

import cv2

from common.config import VisionOSConfig
from common.models import SourceMode
from perception.detector import YOLODetector
from runtime.io import ReplayFrameSource, VideoFrameSource, WebcamFrameSource
from setupux.models import ValidationCheck, ValidationReport, ValidationStatus


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
    source_detail, source_status = _probe_source(config)
    checks = [
        ValidationCheck(name="source", status=source_status, detail=source_detail),
        _check_output_paths(config),
    ]
    if include_model_check:
        checks.append(_check_model(config))
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
