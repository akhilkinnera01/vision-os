"""Tests for canonical trigger config parsing and compatibility loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from integrations import IntegrationConfigError, load_trigger_config


def test_load_trigger_config_parses_canonical_rule(tmp_path: Path) -> None:
    config_path = tmp_path / "triggers.yaml"
    config_path.write_text(
        """
triggers:
  - id: focus-session
    enabled: true
    when:
      source: decision.label
      operator: equals
      value: Focused Work
      min_duration_seconds: 300
    then:
      - type: file_append
        path: out/focus.jsonl
      - type: stdout
    cooldown_seconds: 600
    rearm_on_clear: true
""".strip(),
        encoding="utf-8",
    )

    config = load_trigger_config(str(config_path))

    assert len(config.rules) == 1
    rule = config.rules[0]
    assert rule.rule_id == "focus-session"
    assert rule.enabled is True
    assert rule.condition.source == "decision.label"
    assert rule.condition.operator == "equals"
    assert rule.condition.value == "Focused Work"
    assert rule.condition.min_duration_seconds == 300
    assert rule.cooldown_seconds == 600
    assert rule.rearm_on_clear is True
    assert [action.action_type for action in rule.actions] == ["file_append", "stdout"]
    assert rule.actions[0].target == "out/focus.jsonl"


def test_load_trigger_config_maps_legacy_event_rule_into_canonical_shape(tmp_path: Path) -> None:
    config_path = tmp_path / "legacy-triggers.yaml"
    config_path.write_text(
        """
triggers:
  - id: desk-a-focus-log
    event_type: zone_focus_started
    zone_id: desk_a
    log_path: out/zone-events.jsonl
""".strip(),
        encoding="utf-8",
    )

    config = load_trigger_config(str(config_path))

    assert len(config.rules) == 1
    rule = config.rules[0]
    assert rule.condition.source == "event.event_type"
    assert rule.condition.operator == "equals"
    assert rule.condition.value == "zone_focus_started"
    assert rule.condition.event_metadata_filters == {"zone_id": "desk_a"}
    assert len(rule.actions) == 1
    assert rule.actions[0].action_type == "file_append"
    assert rule.actions[0].target == "out/zone-events.jsonl"


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ("min_duration_seconds: -1", "must be >= 0"),
        ("min_duration_seconds: nope", "must be numeric"),
    ],
)
def test_load_trigger_config_rejects_invalid_min_duration_seconds(
    tmp_path: Path,
    replacement: str,
    message: str,
) -> None:
    config_path = tmp_path / "triggers.yaml"
    config_path.write_text(
        f"""
triggers:
  - id: focus-session
    when:
      source: decision.label
      operator: equals
      value: Focused Work
      {replacement}
    then:
      - type: stdout
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(IntegrationConfigError, match=message):
        load_trigger_config(str(config_path))


def test_load_trigger_config_rejects_min_duration_for_event_rules(tmp_path: Path) -> None:
    config_path = tmp_path / "triggers.yaml"
    config_path.write_text(
        """
triggers:
  - id: distraction-alert
    when:
      source: event.event_type
      operator: equals
      value: distraction_started
      min_duration_seconds: 5
    then:
      - type: stdout
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(IntegrationConfigError, match="do not support min_duration_seconds"):
        load_trigger_config(str(config_path))


def test_load_trigger_config_rejects_invalid_cooldown_seconds(tmp_path: Path) -> None:
    config_path = tmp_path / "triggers.yaml"
    config_path.write_text(
        """
triggers:
  - id: focus-session
    when:
      source: decision.label
      operator: equals
      value: Focused Work
    then:
      - type: stdout
    cooldown_seconds: -1
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(IntegrationConfigError, match="cooldown_seconds"):
        load_trigger_config(str(config_path))


def test_load_trigger_config_rejects_unsupported_source(tmp_path: Path) -> None:
    config_path = tmp_path / "triggers.yaml"
    config_path.write_text(
        """
triggers:
  - id: bad-source
    when:
      source: scene.label
      operator: equals
      value: Focused Work
    then:
      - type: stdout
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(IntegrationConfigError, match="unsupported source"):
        load_trigger_config(str(config_path))


def test_load_trigger_config_rejects_unsupported_operator(tmp_path: Path) -> None:
    config_path = tmp_path / "triggers.yaml"
    config_path.write_text(
        """
triggers:
  - id: bad-operator
    when:
      source: decision.label
      operator: contains
      value: Focused Work
    then:
      - type: stdout
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(IntegrationConfigError, match="unsupported operator"):
        load_trigger_config(str(config_path))
