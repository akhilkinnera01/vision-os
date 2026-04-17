"""Easy Setup tests for generic integrations support."""

from __future__ import annotations

from pathlib import Path

from common.config import VisionOSConfig
from common.models import OverlayMode, SourceMode
from setupux.config_file import load_runtime_config_file, write_starter_bundle
from setupux.summary import collect_runtime_hints, format_startup_summary
from setupux.validate import ValidationStatus, validate_runtime_setup


def test_load_runtime_config_file_resolves_relative_integrations_path(tmp_path: Path) -> None:
    replay_path = tmp_path / "session.jsonl"
    replay_path.write_text("{}\n", encoding="utf-8")
    integrations_path = tmp_path / "visionos.integrations.yaml"
    integrations_path.write_text("integrations: []\n", encoding="utf-8")
    config_path = tmp_path / "visionos.config.yaml"
    config_path.write_text(
        """
source: replay
input: session.jsonl
integrations_file: visionos.integrations.yaml
""".strip()
        + "\n",
        encoding="utf-8",
    )

    config = load_runtime_config_file(str(config_path))

    assert config.source_mode == SourceMode.REPLAY
    assert config.integrations_path == str(integrations_path)


def test_validate_runtime_setup_reports_integration_targets(monkeypatch, tmp_path: Path) -> None:
    replay_path = tmp_path / "session.jsonl"
    replay_path.write_text("{}\n", encoding="utf-8")
    config = VisionOSConfig(
        source_mode=SourceMode.REPLAY,
        input_path=str(replay_path),
        integrations_path=str(tmp_path / "integrations.yaml"),
    )

    monkeypatch.setattr(
        "setupux.validate._probe_source",
        lambda resolved_config: ("Read 1 frame from replay input", ValidationStatus.OK),
    )
    monkeypatch.setattr(
        "setupux.validate.load_integration_config",
        lambda path: type("IntegrationConfig", (), {"targets": ("status", "summary")})(),
    )

    report = validate_runtime_setup(config, include_model_check=False)
    checks = {check.name: check for check in report.checks}

    assert checks["integrations"].status == ValidationStatus.OK
    assert "2 integration" in checks["integrations"].detail


def test_setup_bundle_writes_integrations_template_without_enabling_it(tmp_path: Path) -> None:
    bundle = write_starter_bundle(
        output_dir=str(tmp_path),
        source_mode=SourceMode.WEBCAM,
        camera_index=0,
        profile_name="workstation",
        overlay_mode=OverlayMode.COMPACT,
    )

    assert Path(bundle.integrations_path).is_file()
    assert "integrations: []" in Path(bundle.integrations_path).read_text(encoding="utf-8")

    config = load_runtime_config_file(bundle.config_path)

    assert config.integrations_path is None


def test_startup_summary_reports_integration_count_and_hint() -> None:
    config = VisionOSConfig(source_mode=SourceMode.REPLAY, input_path="demo/demo-replay.jsonl", headless=True)

    output = format_startup_summary(
        config,
        policy_name="default",
        zone_count=0,
        trigger_count=0,
        integration_count=0,
        profile_id=None,
    )
    hints = collect_runtime_hints(config, zone_count=0, trigger_count=0, integration_count=0)

    assert "Integrations: 0 enabled" in output
    assert "No integrations configured; external dispatch is disabled." in hints
