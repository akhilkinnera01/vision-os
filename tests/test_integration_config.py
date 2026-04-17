"""Tests for generic integration config parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

from integrations import IntegrationConfigError
from integrations.config import load_integration_config


def test_load_integration_config_parses_generic_targets(tmp_path: Path) -> None:
    config_path = tmp_path / "integrations.yaml"
    config_path.write_text(
        """
integrations:
  - id: trigger-stdout
    type: stdout
    source: trigger
    trigger_ids: [focus-session]

  - id: event-log
    type: file_append
    source: event
    event_types: [distraction_started, distraction_resolved]
    path: out/events.jsonl

  - id: status-webhook
    type: webhook
    source: status
    interval_seconds: 5
    method: PATCH
    url: https://example.invalid/status

  - id: summary-mqtt
    type: mqtt_publish
    source: session_summary
    host: 127.0.0.1
    port: 1883
    topic: visionos/summary
""".strip(),
        encoding="utf-8",
    )

    config = load_integration_config(str(config_path))

    assert [target.integration_id for target in config.targets] == [
        "trigger-stdout",
        "event-log",
        "status-webhook",
        "summary-mqtt",
    ]
    assert config.targets[0].source == "trigger"
    assert config.targets[0].trigger_ids == ("focus-session",)
    assert config.targets[1].event_types == ("distraction_started", "distraction_resolved")
    assert config.targets[2].interval_seconds == 5.0
    assert config.targets[2].method == "PATCH"
    assert config.targets[3].mqtt_topic == "visionos/summary"


def test_load_integration_config_allows_empty_target_list(tmp_path: Path) -> None:
    config_path = tmp_path / "integrations.yaml"
    config_path.write_text("integrations: []\n", encoding="utf-8")

    config = load_integration_config(str(config_path))

    assert config.targets == ()


def test_load_integration_config_rejects_unsupported_source(tmp_path: Path) -> None:
    config_path = tmp_path / "integrations.yaml"
    config_path.write_text(
        """
integrations:
  - id: bad-source
    type: stdout
    source: decision
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(IntegrationConfigError, match="unsupported source"):
        load_integration_config(str(config_path))


def test_load_integration_config_rejects_status_targets_without_interval(tmp_path: Path) -> None:
    config_path = tmp_path / "integrations.yaml"
    config_path.write_text(
        """
integrations:
  - id: missing-interval
    type: file_append
    source: status
    path: out/status.jsonl
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(IntegrationConfigError, match="interval_seconds"):
        load_integration_config(str(config_path))
