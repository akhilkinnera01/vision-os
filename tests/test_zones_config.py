"""Tests for zone configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from zones import ZoneConfigError, ZoneType, load_zones


def test_load_zones_preserves_order_and_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "zones.yaml"
    config_path.write_text(
        """
zones:
  - id: desk_a
    name: Desk A
    type: occupancy
    polygon:
      - [80, 120]
      - [300, 120]
      - [300, 420]
      - [80, 420]
  - id: whiteboard
    name: Whiteboard
    type: activity
    enabled: false
    labels_of_interest: [person, laptop]
    profile: study-room
    polygon:
      - [320, 80]
      - [620, 80]
      - [620, 300]
      - [320, 300]
""".strip(),
        encoding="utf-8",
    )

    zones = load_zones(str(config_path))

    assert [zone.zone_id for zone in zones] == ["desk_a", "whiteboard"]
    assert zones[0].zone_type == ZoneType.OCCUPANCY
    assert zones[0].enabled is True
    assert zones[1].zone_type == ZoneType.ACTIVITY
    assert zones[1].enabled is False
    assert zones[1].labels_of_interest == ("person", "laptop")
    assert zones[1].profile == "study-room"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("zones: []\n", "non-empty 'zones' list"),
        (
            """
zones:
  - id: desk_a
    type: occupancy
    polygon:
      - [0, 0]
      - [1, 0]
      - [0, 1]
""",
            "'name'",
        ),
        (
            """
zones:
  - id: desk_a
    name: Desk A
    type: occupancy
    polygon:
      - [0, 0]
      - [1, 0]
""",
            "at least 3 points",
        ),
        (
            """
zones:
  - id: desk_a
    name: Desk A
    type: queue
    polygon:
      - [0, 0]
      - [1, 0]
      - [0, 1]
""",
            "unsupported type",
        ),
        (
            """
zones:
  - id: desk_a
    name: Desk A
    type: occupancy
    polygon:
      - [0, 0]
      - [-1, 0]
      - [0, 1]
""",
            "non-negative coordinates",
        ),
        (
            """
zones:
  - id: desk_a
    name: Desk A
    type: occupancy
    polygon:
      - [0, 0]
      - [1, 1]
      - [2, 2]
""",
            "non-zero area",
        ),
        (
            """
zones:
  - id: desk_a
    name: Desk A
    type: occupancy
    polygon:
      - [0, 0]
      - [1, 0]
      - [0, 1]
  - id: desk_a
    name: Desk A 2
    type: activity
    polygon:
      - [2, 2]
      - [3, 2]
      - [2, 3]
""",
            "Duplicate zone id",
        ),
    ],
)
def test_load_zones_rejects_invalid_definitions(tmp_path: Path, body: str, message: str) -> None:
    config_path = tmp_path / "zones.yaml"
    config_path.write_text(body.strip() + "\n", encoding="utf-8")

    with pytest.raises(ZoneConfigError, match=message):
        load_zones(str(config_path))
