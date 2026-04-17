"""Tests for the interactive Easy Setup wizard."""

from __future__ import annotations

from pathlib import Path

from common.models import OverlayMode, SourceMode
from setupux import load_runtime_config_file
from setupux.models import ValidationCheck, ValidationReport, ValidationStatus
from setupux.wizard import run_setup_wizard


def test_run_setup_wizard_writes_bundle_and_prints_validation(tmp_path: Path) -> None:
    answers = iter(
        [
            ".",  # output dir
            "replay",
            "demo/demo-replay.jsonl",
            "meeting_room",
            "debug",
        ]
    )
    lines: list[str] = []
    captured = {}

    def _fake_validate(config, include_model_check=True):
        captured["config"] = config
        captured["include_model_check"] = include_model_check
        return ValidationReport(
            checks=(
                ValidationCheck(
                    name="source",
                    status=ValidationStatus.OK,
                    detail="Read 1 frame from replay input",
                ),
            )
        )

    result = run_setup_wizard(
        input_func=lambda prompt: next(answers),
        output_func=lines.append,
        cwd=str(tmp_path),
        validate_func=_fake_validate,
    )

    config = load_runtime_config_file(result.bundle.config_path)
    assert Path(result.bundle.config_path).is_file()
    assert Path(result.bundle.zones_path).is_file()
    assert Path(result.bundle.trigger_path).is_file()
    assert config.source_mode == SourceMode.REPLAY
    assert config.input_path == str((tmp_path / "demo" / "demo-replay.jsonl").resolve())
    assert config.profile_name == "meeting_room"
    assert config.overlay_mode == OverlayMode.DEBUG
    assert captured["config"].config_path == result.bundle.config_path
    assert captured["include_model_check"] is True
    assert any("Validation summary" in line for line in lines)
    assert any("Run it with: python app.py --config" in line for line in lines)


def test_run_setup_wizard_surfaces_detected_cameras(monkeypatch, tmp_path: Path) -> None:
    answers = iter(
        [
            ".",
            "webcam",
            "",  # accept detected default camera
            "workstation",
            "compact",
        ]
    )
    lines: list[str] = []

    monkeypatch.setattr("setupux.wizard.discover_camera_indexes", lambda max_index=5: [2, 4])

    result = run_setup_wizard(
        input_func=lambda prompt: next(answers),
        output_func=lines.append,
        cwd=str(tmp_path),
        validate_func=lambda config, include_model_check=True: ValidationReport(checks=()),
    )

    config = load_runtime_config_file(result.bundle.config_path)
    assert config.camera_index == 2
    assert any("Detected cameras: 2, 4" in line for line in lines)
