"""Policy loading and validation for runtime thresholds and weights."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class PolicyValidationError(ValueError):
    """Raised when a policy file is missing required sections or values."""


@dataclass(slots=True, frozen=True)
class TrackingPolicy:
    max_idle_seconds: float = 1.5
    min_iou: float = 0.2
    max_center_distance: float = 0.12


@dataclass(slots=True, frozen=True)
class FeaturePolicy:
    laptop_near_person_distance: float = 0.22
    phone_near_person_distance: float = 0.18
    people_cluster_reference_distance: float = 0.35
    centered_monitor_min_area_ratio: float = 0.05
    centered_monitor_axis_score_min: float = 0.65
    desk_bottom_half_ratio: float = 0.33


@dataclass(slots=True, frozen=True)
class TemporalPolicy:
    focus_reference_seconds: float = 8.0
    distraction_spike_delta: float = 0.22
    collaboration_increasing_delta: float = 0.18
    instability_threshold: float = 0.5
    instability_switch_count: int = 3


@dataclass(slots=True, frozen=True)
class DecisionPolicy:
    switch_confirmations: int = 2
    focus_margin: float = 0.08
    collaboration_margin: float = 0.02
    unstable_confidence_penalty: float = 0.12


@dataclass(slots=True, frozen=True)
class EventPolicy:
    focus_sustained_seconds: float = 6.0
    distraction_start_threshold: float = 0.6
    group_person_count: int = 2


@dataclass(slots=True, frozen=True)
class VisionPolicy:
    name: str
    tracking: TrackingPolicy
    features: FeaturePolicy
    temporal: TemporalPolicy
    decision: DecisionPolicy
    events: EventPolicy


def load_policy(name: str = "default", path: str | None = None) -> VisionPolicy:
    """Load and validate a named or explicit YAML policy."""
    policy_path = Path(path) if path else _policy_root() / f"{name}.yaml"
    if not policy_path.is_file():
        raise PolicyValidationError(f"Policy file not found: {policy_path}")

    payload = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise PolicyValidationError(f"Policy root must be a mapping: {policy_path}")

    policy_name = str(payload.get("name", name))
    return VisionPolicy(
        name=policy_name,
        tracking=TrackingPolicy(**_require_section(payload, "tracking")),
        features=FeaturePolicy(**_require_section(payload, "features")),
        temporal=TemporalPolicy(**_require_section(payload, "temporal")),
        decision=DecisionPolicy(**_require_section(payload, "decision")),
        events=EventPolicy(**_require_section(payload, "events")),
    )


def _policy_root() -> Path:
    return Path(__file__).resolve().parent.parent / "policies"


def _require_section(payload: dict[str, object], key: str) -> dict[str, object]:
    section = payload.get(key)
    if not isinstance(section, dict):
        raise PolicyValidationError(f"Policy must define a '{key}' mapping.")
    _validate_numeric_values(section, prefix=key)
    return section


def _validate_numeric_values(section: dict[str, object], prefix: str) -> None:
    for key, value in section.items():
        if isinstance(value, bool):
            continue
        if not isinstance(value, int | float):
            raise PolicyValidationError(f"Policy value '{prefix}.{key}' must be numeric.")
        if value < 0:
            raise PolicyValidationError(f"Policy value '{prefix}.{key}' must be >= 0.")
