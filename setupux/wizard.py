"""Interactive helpers for the Easy Setup onboarding flow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from common.models import OverlayMode, SourceMode
from setupux.config_file import load_runtime_config_file, write_starter_bundle
from setupux.models import SetupBundle, ValidationReport
from setupux.summary import format_validation_report
from setupux.validate import discover_camera_indexes, validate_runtime_setup


BUILTIN_PROFILE_CHOICES = (
    "workstation",
    "study_room",
    "meeting_room",
    "lab_bench",
    "waiting_area",
)


@dataclass(slots=True, frozen=True)
class SetupWizardResult:
    """Artifacts and validation produced by the guided setup flow."""

    bundle: SetupBundle
    validation_report: ValidationReport


def run_setup_wizard(
    *,
    input_func: Callable[[str], str] = input,
    output_func: Callable[[str], None] = print,
    cwd: str | None = None,
    validate_func: Callable[..., ValidationReport] = validate_runtime_setup,
) -> SetupWizardResult:
    """Collect a few high-value choices, write starter files, and validate them."""
    root = Path(cwd or Path.cwd()).resolve()
    output_func("Vision OS setup")
    output_func("This guided flow writes a starter config plus optional zone and trigger templates.")

    bundle_dir = _resolve_path(root, _prompt(input_func, "Setup output directory", "."))
    source_mode = SourceMode(
        _prompt_choice(
            input_func,
            "Source mode",
            choices=tuple(mode.value for mode in SourceMode),
            default=SourceMode.WEBCAM.value,
        )
    )
    camera_index = 0
    input_path = None
    if source_mode == SourceMode.WEBCAM:
        available_cameras = discover_camera_indexes()
        if available_cameras:
            output_func("Detected cameras: " + ", ".join(str(index) for index in available_cameras))
        else:
            output_func("Detected cameras: none")
        camera_default = str(available_cameras[0]) if available_cameras else "0"
        camera_index = int(_prompt(input_func, "Camera index", camera_default))
    else:
        input_path = str(_resolve_path(root, _prompt(input_func, "Input path", "")))

    profile_name = _prompt_choice(
        input_func,
        "Profile",
        choices=BUILTIN_PROFILE_CHOICES,
        default="workstation",
    )
    overlay_mode = OverlayMode(
        _prompt_choice(
            input_func,
            "Overlay mode",
            choices=tuple(mode.value for mode in OverlayMode),
            default=OverlayMode.COMPACT.value,
        )
    )

    output_dir = bundle_dir / "out"
    bundle = write_starter_bundle(
        output_dir=str(bundle_dir),
        source_mode=source_mode,
        camera_index=camera_index,
        input_path=input_path,
        profile_name=profile_name,
        overlay_mode=overlay_mode,
        benchmark_output_path=str(output_dir / "benchmark.json"),
        history_output_path=str(output_dir / "history.jsonl"),
        session_summary_output_path=str(output_dir / "session-summary.json"),
    )
    config = load_runtime_config_file(bundle.config_path)
    report = validate_func(config, include_model_check=True)

    output_func(f"Saved config: {bundle.config_path}")
    output_func(f"Starter zones template: {bundle.zones_path}")
    output_func(f"Starter triggers template: {bundle.trigger_path}")
    output_func(format_validation_report(report))
    output_func(f"Run it with: python app.py --config {bundle.config_path}")
    return SetupWizardResult(bundle=bundle, validation_report=report)


def _prompt(input_func: Callable[[str], str], label: str, default: str) -> str:
    while True:
        value = input_func(f"{label} [{default}]: ").strip()
        if value:
            return value
        if default:
            return default


def _prompt_choice(
    input_func: Callable[[str], str],
    label: str,
    *,
    choices: tuple[str, ...],
    default: str,
) -> str:
    normalized_choices = {choice.lower(): choice for choice in choices}
    prompt = f"{label} ({'/'.join(choices)}) [{default}]: "
    while True:
        raw_value = input_func(prompt).strip()
        if not raw_value:
            return default
        choice = normalized_choices.get(raw_value.lower())
        if choice is not None:
            return choice


def _resolve_path(base_dir: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    return path if path.is_absolute() else (base_dir / path).resolve()
