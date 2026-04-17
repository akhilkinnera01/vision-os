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
