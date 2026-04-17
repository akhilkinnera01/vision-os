"""Load and validate static zone definitions from YAML."""

from __future__ import annotations

from pathlib import Path

import yaml

from zones.models import Zone, ZonePoint, ZoneType


class ZoneConfigError(ValueError):
    """Raised when a zones file is malformed or unsupported."""


def load_zones(path: str) -> tuple[Zone, ...]:
    """Load a zone file and return validated zones in source order."""
    zone_path = Path(path)
    if not zone_path.is_file():
        raise ZoneConfigError(f"Zone config not found: {zone_path}")

    payload = yaml.safe_load(zone_path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ZoneConfigError(f"Zone config root must be a mapping: {zone_path}")

    raw_zones = payload.get("zones")
    if not isinstance(raw_zones, list) or not raw_zones:
        raise ZoneConfigError("Zone config must define a non-empty 'zones' list.")

    zones: list[Zone] = []
    seen_ids: set[str] = set()
    for index, raw_zone in enumerate(raw_zones):
        zone = _parse_zone(raw_zone, index)
        if zone.zone_id in seen_ids:
            raise ZoneConfigError(f"Duplicate zone id: {zone.zone_id}")
        seen_ids.add(zone.zone_id)
        zones.append(zone)
    return tuple(zones)


def select_zones_for_profile(zones: tuple[Zone, ...], active_profile: str | None) -> tuple[Zone, ...]:
    """Keep shared zones plus zones scoped to the selected runtime profile."""
    if active_profile is None:
        return tuple(zones)
    return tuple(zone for zone in zones if zone.profile is None or zone.profile == active_profile)


def _parse_zone(payload: object, index: int) -> Zone:
    if not isinstance(payload, dict):
        raise ZoneConfigError(f"Zone at index {index} must be a mapping.")

    zone_id = _require_string(payload, "id", index)
    name = _require_string(payload, "name", index)
    raw_type = _require_string(payload, "type", index)
    try:
        zone_type = ZoneType(raw_type)
    except ValueError as exc:
        raise ZoneConfigError(
            f"Zone '{zone_id}' has unsupported type '{raw_type}'."
        ) from exc

    polygon = _parse_polygon(payload.get("polygon"), zone_id)
    enabled = payload.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ZoneConfigError(f"Zone '{zone_id}' field 'enabled' must be a boolean.")

    raw_labels = payload.get("labels_of_interest", [])
    if not isinstance(raw_labels, list) or any(not isinstance(label, str) or not label.strip() for label in raw_labels):
        raise ZoneConfigError(f"Zone '{zone_id}' field 'labels_of_interest' must be a list of strings.")

    raw_profile = payload.get("profile")
    if raw_profile is not None and (not isinstance(raw_profile, str) or not raw_profile.strip()):
        raise ZoneConfigError(f"Zone '{zone_id}' field 'profile' must be a non-empty string when present.")

    return Zone(
        zone_id=zone_id,
        name=name,
        zone_type=zone_type,
        polygon=polygon,
        enabled=enabled,
        labels_of_interest=tuple(raw_labels),
        profile=raw_profile,
    )


def _require_string(payload: dict[str, object], key: str, index: int) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ZoneConfigError(f"Zone at index {index} must define a non-empty '{key}' field.")
    return value.strip()


def _parse_polygon(payload: object, zone_id: str) -> tuple[ZonePoint, ...]:
    if not isinstance(payload, list) or len(payload) < 3:
        raise ZoneConfigError(f"Zone '{zone_id}' must define a polygon with at least 3 points.")

    points: list[ZonePoint] = []
    seen: set[tuple[float, float]] = set()
    for point_index, raw_point in enumerate(payload):
        if not isinstance(raw_point, list | tuple) or len(raw_point) != 2:
            raise ZoneConfigError(f"Zone '{zone_id}' point {point_index} must be a 2-item coordinate.")
        x, y = raw_point
        if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, int | float) or not isinstance(y, int | float):
            raise ZoneConfigError(f"Zone '{zone_id}' point {point_index} must contain numeric coordinates.")
        if x < 0 or y < 0:
            raise ZoneConfigError(f"Zone '{zone_id}' point {point_index} must use non-negative coordinates.")
        key = (float(x), float(y))
        seen.add(key)
        points.append(ZonePoint(*key))

    if len(seen) < 3:
        raise ZoneConfigError(f"Zone '{zone_id}' polygon must contain at least 3 unique points.")
    if _signed_area(points) == 0.0:
        raise ZoneConfigError(f"Zone '{zone_id}' polygon must enclose a non-zero area.")
    return tuple(points)


def _signed_area(points: list[ZonePoint]) -> float:
    total = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        total += point.x * nxt.y
        total -= nxt.x * point.y
    return total / 2.0
