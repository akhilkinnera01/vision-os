"""Tests for Easy Setup CLI helper modes."""

from __future__ import annotations

import sys

import app
from common.config import VisionOSConfig


def test_parse_args_accepts_list_cameras(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["app.py", "--list-cameras"])

    config = app.parse_args()

    assert config.list_cameras is True


def test_main_lists_cameras_and_exits(monkeypatch, capsys) -> None:
    config = VisionOSConfig(list_cameras=True)

    monkeypatch.setattr(app, "parse_args", lambda: config)
    monkeypatch.setattr(app, "discover_camera_indexes", lambda max_index=5: [0, 2])

    assert app.main() == 0

    captured = capsys.readouterr()
    assert "Available cameras: 0, 2" in captured.out
