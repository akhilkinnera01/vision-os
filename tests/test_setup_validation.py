"""Tests for Easy Setup validation and camera discovery helpers."""

from __future__ import annotations

from pathlib import Path

from common.config import VisionOSConfig
from common.models import SourceMode
from setupux.validate import ValidationStatus, discover_camera_indexes, validate_runtime_setup


def test_discover_camera_indexes_reports_only_open_devices(monkeypatch) -> None:
    opened = {0: True, 1: False, 2: True}

    class FakeCapture:
        def __init__(self, index: int) -> None:
            self.index = index

        def isOpened(self) -> bool:
            return opened.get(self.index, False)

        def release(self) -> None:
            pass

    monkeypatch.setattr("setupux.validate.cv2.VideoCapture", FakeCapture)

    assert discover_camera_indexes(max_index=4) == [0, 2]


def test_validate_runtime_setup_reports_source_and_output_checks(monkeypatch, tmp_path: Path) -> None:
    replay_path = tmp_path / "session.jsonl"
    replay_path.write_text("{}\n", encoding="utf-8")
    config = VisionOSConfig(
        source_mode=SourceMode.REPLAY,
        input_path=str(replay_path),
        benchmark_output_path=str(tmp_path / "out" / "benchmark.json"),
        history_output_path=str(tmp_path / "out" / "history.jsonl"),
        session_summary_output_path=str(tmp_path / "out" / "session-summary.json"),
    )

    monkeypatch.setattr(
        "setupux.validate._probe_source",
        lambda resolved_config: ("Read 1 frame from replay input", ValidationStatus.OK),
    )

    report = validate_runtime_setup(config, include_model_check=False)
    checks = {check.name: check for check in report.checks}

    assert checks["source"].status == ValidationStatus.OK
    assert "Read 1 frame" in checks["source"].detail
    assert checks["outputs"].status == ValidationStatus.OK
    assert (tmp_path / "out").is_dir()
    assert checks["model"].status == ValidationStatus.SKIPPED
