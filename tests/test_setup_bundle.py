"""Tests for Easy Setup starter bundle generation."""

from __future__ import annotations

from pathlib import Path

from common.config import VisionOSConfig
from common.models import OverlayMode, SourceMode
from setupux.config_file import load_runtime_config_file, write_runtime_config_file, write_starter_bundle


def test_write_runtime_config_file_uses_relative_bundle_paths(tmp_path: Path) -> None:
    zones_path = tmp_path / "visionos.zones.yaml"
    triggers_path = tmp_path / "visionos.triggers.yaml"
    config_path = tmp_path / "visionos.config.yaml"

    config = VisionOSConfig(
        source_mode=SourceMode.WEBCAM,
        camera_index=1,
        profile_name="workstation",
        overlay_mode=OverlayMode.DEBUG,
        zones_path=str(zones_path),
        trigger_path=str(triggers_path),
        benchmark_output_path=str(tmp_path / "out" / "benchmark.json"),
    )

    write_runtime_config_file(config, str(config_path))

    payload = config_path.read_text(encoding="utf-8")
    assert "zones_file: visionos.zones.yaml" in payload
    assert "trigger_file: visionos.triggers.yaml" in payload
    assert "benchmark_output: out/benchmark.json" in payload


def test_write_starter_bundle_creates_config_and_stub_assets(tmp_path: Path) -> None:
    bundle = write_starter_bundle(
        output_dir=str(tmp_path),
        source_mode=SourceMode.WEBCAM,
        camera_index=0,
        profile_name="workstation",
        overlay_mode=OverlayMode.COMPACT,
    )

    assert Path(bundle.config_path).is_file()
    assert Path(bundle.zones_path).is_file()
    assert Path(bundle.trigger_path).is_file()

    config = load_runtime_config_file(bundle.config_path)
    assert config.source_mode == SourceMode.WEBCAM
    assert config.profile_name == "workstation"
    assert config.zones_path is None
    assert config.trigger_path is None
    assert "zones: []" in Path(bundle.zones_path).read_text(encoding="utf-8")
    assert "triggers: []" in Path(bundle.trigger_path).read_text(encoding="utf-8")
