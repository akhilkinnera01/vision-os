"""Tests for runtime profile loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from common.profile import ProfileValidationError, load_profile
from common.models import OverlayMode


def test_load_profile_reads_builtin_workstation_profile() -> None:
    profile = load_profile(name="workstation")

    assert profile.profile_id == "workstation"
    assert profile.policy_name == "office"
    assert profile.presentation.overlay_mode == OverlayMode.COMPACT
    assert "Focused Work" in profile.scene_labels


def test_load_profile_rejects_unknown_builtin_profile() -> None:
    with pytest.raises(ProfileValidationError, match="Profile file not found"):
        load_profile(name="not-a-real-profile")


def test_load_profile_resolves_relative_trigger_paths(tmp_path: Path) -> None:
    triggers_path = tmp_path / "triggers.yaml"
    triggers_path.write_text(
        """
triggers:
  - id: focus-log
    when:
      source: decision.label
      operator: equals
      value: Focused Work
    then:
      - type: stdout
""".strip(),
        encoding="utf-8",
    )
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        """
id: custom
name: Custom
description: Custom profile
policy: default
trigger_file: triggers.yaml
presentation:
  overlay_mode: debug
  compact_sections: [scores, triggers]
  debug_sections: [scores, events, triggers]
scene_labels:
  - Focused Work
""".strip(),
        encoding="utf-8",
    )

    profile = load_profile(path=str(profile_path))

    assert profile.trigger_path == str(triggers_path)


def test_load_profile_rejects_unknown_overlay_section(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        """
id: custom
name: Custom
description: Custom profile
policy: default
presentation:
  overlay_mode: compact
  compact_sections: [scores, nonsense]
scene_labels:
  - Focused Work
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ProfileValidationError, match="compact_sections"):
        load_profile(path=str(profile_path))


def test_load_profile_resolves_relative_policy_files(tmp_path: Path) -> None:
    policy_path = tmp_path / "policies" / "study-room.yaml"
    policy_path.parent.mkdir()
    policy_path.write_text(
        """
name: study-room
tracking:
  max_idle_seconds: 1.5
  min_iou: 0.2
  max_center_distance: 0.12
features:
  laptop_near_person_distance: 0.22
  phone_near_person_distance: 0.18
  people_cluster_reference_distance: 0.35
  centered_monitor_min_area_ratio: 0.05
  centered_monitor_axis_score_min: 0.65
  desk_bottom_half_ratio: 0.33
temporal:
  focus_reference_seconds: 8.0
  distraction_spike_delta: 0.22
  collaboration_increasing_delta: 0.18
  instability_threshold: 0.5
  instability_switch_count: 3
decision:
  switch_confirmations: 2
  focus_margin: 0.08
  collaboration_margin: 0.02
  unstable_confidence_penalty: 0.12
events:
  focus_sustained_seconds: 6.0
  distraction_start_threshold: 0.6
  group_person_count: 2
""".strip(),
        encoding="utf-8",
    )
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        """
id: custom
name: Custom
description: Custom profile
policy_file: policies/study-room.yaml
scene_labels:
  - Focused Work
""".strip(),
        encoding="utf-8",
    )

    profile = load_profile(path=str(profile_path))

    assert profile.policy_path == str(policy_path)


def test_load_profile_rejects_profiles_with_named_and_file_policy(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("name: custom\n", encoding="utf-8")
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        """
id: custom
name: Custom
description: Custom profile
policy: office
policy_file: policy.yaml
scene_labels:
  - Focused Work
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ProfileValidationError, match="policy_file"):
        load_profile(path=str(profile_path))


@pytest.mark.parametrize(
    "profile_name",
    ["workstation", "study_room", "meeting_room", "lab_bench", "waiting_area"],
)
def test_load_profile_supports_all_builtin_profiles(profile_name: str) -> None:
    profile = load_profile(name=profile_name)

    assert profile.profile_id == profile_name
    assert profile.name


def test_builtin_profiles_reference_packaged_trigger_sets() -> None:
    for profile_name in ["workstation", "study_room", "meeting_room", "lab_bench", "waiting_area"]:
        profile = load_profile(name=profile_name)

        assert profile.trigger_path is not None
        assert Path(profile.trigger_path).is_file()


def test_load_profile_rejects_missing_trigger_reference(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        """
id: custom
name: Custom
description: Custom profile
policy: default
trigger_file: missing.yaml
presentation:
  overlay_mode: compact
  compact_sections: [scores]
scene_labels:
  - Focused Work
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ProfileValidationError, match="trigger_file"):
        load_profile(path=str(profile_path))


def test_load_profile_rejects_unknown_policy_name(tmp_path: Path) -> None:
    profile_path = tmp_path / "profile.yaml"
    profile_path.write_text(
        """
id: custom
name: Custom
description: Custom profile
policy: missing
presentation:
  overlay_mode: compact
  compact_sections: [scores]
scene_labels:
  - Focused Work
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ProfileValidationError, match="policy"):
        load_profile(path=str(profile_path))
