"""Typed zone definitions for zone-aware spatial reasoning."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class ZoneType(StrEnum):
    """Supported V1 zone categories."""

    OCCUPANCY = "occupancy"
    ACTIVITY = "activity"
    TRANSITION = "transition"


@dataclass(slots=True, frozen=True)
class ZonePoint:
    """One polygon vertex in image pixel space."""

    x: float
    y: float

    def to_list(self) -> list[float]:
        return [self.x, self.y]


@dataclass(slots=True, frozen=True)
class Zone:
    """One user-defined named region within the camera frame."""

    zone_id: str
    name: str
    zone_type: ZoneType
    polygon: tuple[ZonePoint, ...]
    enabled: bool = True
    labels_of_interest: tuple[str, ...] = field(default_factory=tuple)
    profile: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "id": self.zone_id,
            "name": self.name,
            "type": self.zone_type.value,
            "polygon": [point.to_list() for point in self.polygon],
            "enabled": self.enabled,
        }
        if self.labels_of_interest:
            payload["labels_of_interest"] = list(self.labels_of_interest)
        if self.profile is not None:
            payload["profile"] = self.profile
        return payload
