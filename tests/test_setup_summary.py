"""Tests for Easy Setup summary formatting."""

from __future__ import annotations

from common.config import VisionOSConfig
from common.models import SourceMode
from setupux.models import ValidationCheck, ValidationReport, ValidationStatus
from setupux.summary import collect_runtime_hints, format_startup_summary, format_validation_report


def test_format_validation_report_renders_status_lines() -> None:
    report = ValidationReport(
        checks=(
            ValidationCheck(name="source", status=ValidationStatus.OK, detail="Read 1 frame from replay input"),
            ValidationCheck(name="model", status=ValidationStatus.SKIPPED, detail="Model check skipped"),
        )
    )

    output = format_validation_report(report)

    assert "Validation summary" in output
    assert "source: OK - Read 1 frame from replay input" in output
    assert "model: SKIPPED - Model check skipped" in output


def test_collect_runtime_hints_reports_missing_optional_assets() -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.WEBCAM,
        camera_index=0,
        benchmark_output_path="out/benchmark.json",
    )

    hints = collect_runtime_hints(config, zone_count=0, trigger_count=0)

    assert "Camera source active." in hints
    assert "No zones configured yet; zone-level state is disabled." in hints
    assert "No triggers enabled; automation outputs are disabled." in hints
    assert "Benchmark summary will be written to out/benchmark.json." in hints


def test_format_startup_summary_renders_runtime_overview() -> None:
    config = VisionOSConfig(
        source_mode=SourceMode.REPLAY,
        input_path="demo/demo-replay.jsonl",
        profile_name="meeting_room",
        benchmark_output_path="out/benchmark.json",
        history_output_path="out/history.jsonl",
        session_summary_output_path="out/session-summary.json",
        headless=True,
    )

    output = format_startup_summary(
        config,
        policy_name="office",
        zone_count=2,
        trigger_count=1,
        profile_id="meeting_room",
    )

    assert "Startup summary" in output
    assert "Source: replay(demo/demo-replay.jsonl)" in output
    assert "Profile: meeting_room" in output
    assert "Policy: office" in output
    assert "Zones: 2 loaded" in output
    assert "Triggers: 1 enabled" in output
    assert "Benchmark: out/benchmark.json" in output
    assert "History: out/history.jsonl" in output
    assert "Session summary: out/session-summary.json" in output
