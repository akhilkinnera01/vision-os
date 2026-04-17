"""Tests for Easy Setup summary formatting."""

from __future__ import annotations

from setupux.models import ValidationCheck, ValidationReport, ValidationStatus
from setupux.summary import format_validation_report


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
