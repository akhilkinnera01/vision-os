"""Runtime profile loading and validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from common.models import ContextLabel, OverlayMode


class ProfileValidationError(ValueError):
    """Raised when a runtime profile is missing required fields or references."""


class OverlaySection(StrEnum):
    """Renderer sections that profiles may emphasize or suppress."""

    SCORES = "scores"
    ZONES = "zones"
    EVENTS = "events"
    TRIGGERS = "triggers"
    RUNTIME = "runtime"
    SPATIAL = "spatial"


@dataclass(slots=True, frozen=True)
class ProfilePresentation:
    """Profile-controlled presentation hints for the overlay layer."""

    overlay_mode: OverlayMode = OverlayMode.COMPACT
    compact_sections: tuple[OverlaySection, ...] = (OverlaySection.SCORES,)
    debug_sections: tuple[OverlaySection, ...] = (
        OverlaySection.SCORES,
        OverlaySection.EVENTS,
        OverlaySection.TRIGGERS,
        OverlaySection.ZONES,
        OverlaySection.RUNTIME,
        OverlaySection.SPATIAL,
    )


@dataclass(slots=True, frozen=True)
class RuntimeProfile:
    """Resolved runtime profile manifest."""

    profile_id: str
    name: str
    description: str
    policy_name: str = "default"
    policy_path: str | None = None
    zones_path: str | None = None
    trigger_path: str | None = None
    scene_labels: tuple[str, ...] = ()
    presentation: ProfilePresentation = ProfilePresentation()


def load_profile(name: str | None = None, path: str | None = None) -> RuntimeProfile:
    """Load a runtime profile from a built-in name or explicit YAML path."""
    profile_path = Path(path) if path else _profile_root() / f"{name}.yaml"
    if not profile_path.is_file():
        raise ProfileValidationError(f"Profile file not found: {profile_path}")

    payload = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ProfileValidationError(f"Profile root must be a mapping: {profile_path}")

    profile_id = _require_string(payload, "id")
    profile_name = _require_string(payload, "name")
    description = _require_string(payload, "description")
    policy_name = str(payload.get("policy", "default"))
    _validate_policy_name(policy_name)
    trigger_path = _resolve_optional_path(profile_path.parent, payload.get("trigger_file"), field_name="trigger_file")
    zones_path = _resolve_optional_path(profile_path.parent, payload.get("zones_file"), field_name="zones_file")
    scene_labels = _string_list(payload.get("scene_labels", []), field_name="scene_labels")
    _validate_scene_labels(scene_labels)
    presentation = _parse_presentation(payload.get("presentation", {}), profile_id)

    return RuntimeProfile(
        profile_id=profile_id,
        name=profile_name,
        description=description,
        policy_name=policy_name,
        policy_path=None,
        zones_path=zones_path,
        trigger_path=trigger_path,
        scene_labels=tuple(scene_labels),
        presentation=presentation,
    )


def _profile_root() -> Path:
    return Path(__file__).resolve().parent.parent / "profiles"


def _require_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProfileValidationError(f"Profile field '{key}' must be a non-empty string.")
    return value.strip()


def _resolve_optional_path(base_dir: Path, value: object, *, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ProfileValidationError(f"Profile field '{field_name}' must be a non-empty string when present.")
    resolved = (base_dir / value).resolve() if not Path(value).is_absolute() else Path(value)
    if not resolved.is_file():
        raise ProfileValidationError(f"Profile field '{field_name}' references a missing file: {value}")
    return str(resolved)


def _string_list(payload: object, *, field_name: str) -> list[str]:
    if not isinstance(payload, list):
        raise ProfileValidationError(f"Profile field '{field_name}' must be a list.")
    result: list[str] = []
    for item in payload:
        if not isinstance(item, str) or not item.strip():
            raise ProfileValidationError(f"Profile field '{field_name}' must only contain non-empty strings.")
        result.append(item.strip())
    return result


def _parse_presentation(payload: object, profile_id: str) -> ProfilePresentation:
    if not isinstance(payload, dict):
        raise ProfileValidationError(f"Profile '{profile_id}' field 'presentation' must be a mapping.")

    overlay_raw = payload.get("overlay_mode", OverlayMode.COMPACT.value)
    try:
        overlay_mode = OverlayMode(str(overlay_raw))
    except ValueError as exc:
        raise ProfileValidationError(
            f"Profile '{profile_id}' field 'presentation.overlay_mode' is invalid: {overlay_raw}"
        ) from exc

    compact_sections = _parse_sections(
        payload.get("compact_sections", [OverlaySection.SCORES.value]),
        profile_id=profile_id,
        field_name="compact_sections",
    )
    debug_sections = _parse_sections(
        payload.get(
            "debug_sections",
            [
                OverlaySection.SCORES.value,
                OverlaySection.EVENTS.value,
                OverlaySection.TRIGGERS.value,
                OverlaySection.ZONES.value,
                OverlaySection.RUNTIME.value,
                OverlaySection.SPATIAL.value,
            ],
        ),
        profile_id=profile_id,
        field_name="debug_sections",
    )
    return ProfilePresentation(
        overlay_mode=overlay_mode,
        compact_sections=tuple(compact_sections),
        debug_sections=tuple(debug_sections),
    )


def _parse_sections(payload: object, *, profile_id: str, field_name: str) -> list[OverlaySection]:
    if not isinstance(payload, list) or not payload:
        raise ProfileValidationError(f"Profile '{profile_id}' field 'presentation.{field_name}' must be a non-empty list.")
    sections: list[OverlaySection] = []
    for item in payload:
        try:
            sections.append(OverlaySection(str(item)))
        except ValueError as exc:
            raise ProfileValidationError(
                f"Profile '{profile_id}' field 'presentation.{field_name}' contains unsupported section '{item}'."
            ) from exc
    return sections


def _validate_policy_name(policy_name: str) -> None:
    policy_path = Path(__file__).resolve().parent.parent / "policies" / f"{policy_name}.yaml"
    if not policy_path.is_file():
        raise ProfileValidationError(f"Profile field 'policy' references an unknown policy: {policy_name}")


def _validate_scene_labels(scene_labels: list[str]) -> None:
    valid_labels = {label.value for label in ContextLabel}
    for label in scene_labels:
        if label not in valid_labels:
            raise ProfileValidationError(f"Profile field 'scene_labels' contains an unknown label: {label}")
