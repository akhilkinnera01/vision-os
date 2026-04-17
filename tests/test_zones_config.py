"""Tests for zone configuration loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from zones import ZoneConfigError, ZoneType, load_zones, select_zones_for_profile


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


def test_select_zones_for_profile_keeps_shared_and_matching_zones(tmp_path: Path) -> None:
    config_path = tmp_path / "zones.yaml"
    config_path.write_text(
        """
zones:
  - id: shared
    name: Shared
    type: occupancy
    polygon:
      - [0, 0]
      - [10, 0]
      - [10, 10]
      - [0, 10]
  - id: study_desk
    name: Study Desk
    type: occupancy
    profile: study_room
    polygon:
      - [20, 0]
      - [30, 0]
      - [30, 10]
      - [20, 10]
  - id: meeting_table
    name: Meeting Table
    type: activity
    profile: meeting_room
    polygon:
      - [40, 0]
      - [50, 0]
      - [50, 10]
      - [40, 10]
""".strip(),
        encoding="utf-8",
    )

    zones = load_zones(str(config_path))

    assert [zone.zone_id for zone in select_zones_for_profile(zones, active_profile="study_room")] == [
        "shared",
        "study_desk",
    ]
    assert [zone.zone_id for zone in select_zones_for_profile(zones, active_profile="meeting_room")] == [
        "shared",
        "meeting_table",
    ]
    assert [zone.zone_id for zone in select_zones_for_profile(zones, active_profile=None)] == [
        "shared",
        "study_desk",
        "meeting_table",
    ]


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
