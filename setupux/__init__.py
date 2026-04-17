"""Easy setup helpers for config loading, validation, and summaries."""

from setupux.config_file import load_runtime_config_file, write_runtime_config_file, write_starter_bundle
from setupux.models import SetupBundle, ValidationCheck, ValidationReport, ValidationStatus
from setupux.summary import collect_runtime_hints, format_startup_summary, format_validation_report
from setupux.validate import discover_camera_indexes, validate_runtime_setup
from setupux.wizard import run_setup_wizard

__all__ = [
    "SetupBundle",
    "ValidationCheck",
    "ValidationReport",
    "ValidationStatus",
    "collect_runtime_hints",
    "discover_camera_indexes",
    "format_startup_summary",
    "format_validation_report",
    "load_runtime_config_file",
    "run_setup_wizard",
    "write_runtime_config_file",
    "write_starter_bundle",
    "validate_runtime_setup",
]
