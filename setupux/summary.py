"""Formatting helpers for Easy Setup summaries and hints."""

from __future__ import annotations

from setupux.models import ValidationReport


def format_validation_report(report: ValidationReport) -> str:
    """Render a validation report as user-facing plain text."""
    lines = ["Validation summary"]
    for check in report.checks:
        lines.append(f"{check.name}: {check.status.value.upper()} - {check.detail}")
    return "\n".join(lines)
