"""Tests for externalized runtime policies."""

from __future__ import annotations

from pathlib import Path

import pytest

from common.policy import PolicyValidationError, load_policy


def test_load_default_policy() -> None:
    policy = load_policy("default")

    assert policy.name == "default"
    assert policy.tracking.max_idle_seconds > 0.0
    assert policy.features.laptop_near_person_distance == 0.22
    assert policy.decision.switch_confirmations == 2


def test_invalid_policy_raises_readable_error(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.yaml"
    invalid_path.write_text(
        "tracking:\n  max_idle_seconds: 1.0\n  min_iou: 0.2\n  max_center_distance: 0.12\n",
        encoding="utf-8",
    )

    with pytest.raises(PolicyValidationError, match="features"):
        load_policy(path=str(invalid_path))
