"""Formatting helpers for Easy Setup summaries and hints."""

from __future__ import annotations

from common.config import VisionOSConfig
from common.models import SourceMode
from setupux.models import ValidationReport


def format_validation_report(report: ValidationReport) -> str:
    """Render a validation report as user-facing plain text."""
    lines = ["Validation summary"]
    for check in report.checks:
        lines.append(f"{check.name}: {check.status.value.upper()} - {check.detail}")
    return "\n".join(lines)


def format_startup_summary(
    config: VisionOSConfig,
    *,
    policy_name: str,
    zone_count: int,
    trigger_count: int,
    profile_id: str | None,
) -> str:
    """Render a human-readable runtime overview before the main loop starts."""
    lines = [
        "Startup summary",
        f"Source: {_describe_source(config)}",
        f"Profile: {profile_id or 'none'}",
        f"Policy: {policy_name}",
        f"Overlay: {config.overlay_mode.value}",
        f"Headless: {str(config.headless).lower()}",
        f"Zones: {zone_count} loaded",
        f"Triggers: {trigger_count} enabled",
        f"Benchmark: {config.benchmark_output_path or 'disabled'}",
        f"History: {config.history_output_path or 'disabled'}",
        f"Session summary: {config.session_summary_output_path or 'disabled'}",
    ]
    hints = collect_runtime_hints(config, zone_count=zone_count, trigger_count=trigger_count)
    if hints:
        lines.append("Hints:")
        for hint in hints:
            lines.append(f"- {hint}")
    return "\n".join(lines)


def collect_runtime_hints(config: VisionOSConfig, *, zone_count: int, trigger_count: int) -> tuple[str, ...]:
    """Collect lightweight operator hints for first-run usability."""
    hints: list[str] = []
    if config.source_mode == SourceMode.WEBCAM:
        hints.append("Camera source active.")
    elif config.source_mode == SourceMode.REPLAY:
        hints.append("Replay mode loaded; repeated runs are deterministic.")
    else:
        hints.append("Video file source active.")

    if zone_count == 0:
        hints.append("No zones configured yet; zone-level state is disabled.")
    if trigger_count == 0:
        hints.append("No triggers enabled; automation outputs are disabled.")
    if config.record_path:
        hints.append(f"Replay artifact will be written to {config.record_path}.")
    if config.benchmark_output_path:
        hints.append(f"Benchmark summary will be written to {config.benchmark_output_path}.")
    if config.history_output_path:
        hints.append(f"History timeline will be written to {config.history_output_path}.")
    if config.session_summary_output_path:
        hints.append(f"Session summary will be written to {config.session_summary_output_path}.")
    return tuple(hints)


def _describe_source(config: VisionOSConfig) -> str:
    if config.source_mode == SourceMode.WEBCAM:
        return f"webcam({config.camera_index})"
    return f"{config.source_mode.value}({config.input_path})"
