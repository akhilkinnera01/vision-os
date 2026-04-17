"""Tests for Easy Setup CLI helper modes."""

from __future__ import annotations

import sys

import app
from common.config import VisionOSConfig


def test_parse_args_accepts_list_cameras(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["app.py", "--list-cameras"])

    config = app.parse_args()

    assert config.list_cameras is True


def test_parse_args_accepts_validate_config(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["app.py", "--validate-config"])

    config = app.parse_args()

    assert config.validate_config is True


def test_main_lists_cameras_and_exits(monkeypatch, capsys) -> None:
    config = VisionOSConfig(list_cameras=True)

    monkeypatch.setattr(app, "parse_args", lambda: config)
    monkeypatch.setattr(app, "discover_camera_indexes", lambda max_index=5: [0, 2])

    assert app.main() == 0

    captured = capsys.readouterr()
    assert "Available cameras: 0, 2" in captured.out


def test_main_runs_validate_config_and_exits(monkeypatch, capsys) -> None:
    config = VisionOSConfig(validate_config=True)

    monkeypatch.setattr(app, "parse_args", lambda: config)
    monkeypatch.setattr(
        app,
        "validate_runtime_setup",
        lambda resolved_config, include_model_check=True: app.ValidationReport(
            checks=(
                app.ValidationCheck(
                    name="source",
                    status=app.ValidationStatus.OK,
                    detail="Read 1 frame from replay input",
                ),
            )
        ),
    )

    assert app.main() == 0

    captured = capsys.readouterr()
    assert "Validation summary" in captured.out
    assert "source: OK - Read 1 frame from replay input" in captured.out
