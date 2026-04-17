"""Dataclasses for Easy Setup validation and starter bundle flows."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ValidationStatus(StrEnum):
    """Status values for setup validation checks."""

    OK = "ok"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass(slots=True, frozen=True)
class ValidationCheck:
    """One named preflight validation result."""

    name: str
    status: ValidationStatus
    detail: str


@dataclass(slots=True, frozen=True)
class ValidationReport:
    """Ordered setup validation results."""

    checks: tuple[ValidationCheck, ...] = field(default_factory=tuple)
