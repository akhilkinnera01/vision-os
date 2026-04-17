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


def test_invalid_policy_raises_readable_error() -> None:
    # Use a path within the policy root for testing invalid content
    root = Path(__file__).resolve().parent.parent / "policies"
    invalid_path = root / "invalid_test_policy.yaml"
    invalid_path.write_text(
        "tracking:\n  max_idle_seconds: 1.0\n  min_iou: 0.2\n  max_center_distance: 0.12\n",
        encoding="utf-8",
    )

    try:
        with pytest.raises(PolicyValidationError, match="features"):
            load_policy(path=str(invalid_path))
    finally:
        invalid_path.unlink(missing_ok=True)


def test_load_policy_traversal_protection() -> None:
    with pytest.raises(PolicyValidationError, match="must be within"):
        load_policy(path="/etc/passwd")

    with pytest.raises(PolicyValidationError, match="must be within"):
        load_policy(name="../app")
