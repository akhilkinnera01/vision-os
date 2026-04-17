"""Tests for trigger matching and integration outputs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from common.models import VisionEvent
from integrations import IntegrationConfigError, TriggerConfig, TriggerEngine, load_trigger_config
from integrations.config import TriggerRule
from telemetry.logging import VisionLogger


def test_load_trigger_config_rejects_invalid_rules(tmp_path: Path) -> None:
    config_path = tmp_path / "triggers.yaml"
    config_path.write_text(
        """
triggers:
  - id: zone-focus
    event_type: zone_focus_started
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(IntegrationConfigError, match="at least one output target"):
        load_trigger_config(str(config_path))


def test_trigger_engine_writes_log_for_matching_zone_event(tmp_path: Path) -> None:
    log_path = tmp_path / "events" / "zone-events.jsonl"
    engine = TriggerEngine(
        TriggerConfig(
            rules=(
                TriggerRule(
                    rule_id="desk-a-focus",
                    event_type="zone_focus_started",
                    zone_id="desk_a",
                    log_path=str(log_path),
                ),
            )
        )
    )
    event = VisionEvent(
        event_type="zone_focus_started",
        timestamp=1.0,
        description="Desk A entered solo focus",
        metadata={"zone_id": "desk_a"},
    )

    engine.dispatch([event])

    payload = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
    assert payload["trigger_id"] == "desk-a-focus"
    assert payload["event"]["event_type"] == "zone_focus_started"


def test_trigger_engine_ignores_non_matching_zone_events(tmp_path: Path) -> None:
    log_path = tmp_path / "events.jsonl"
    engine = TriggerEngine(
        TriggerConfig(
            rules=(
                TriggerRule(
                    rule_id="desk-a-focus",
                    event_type="zone_focus_started",
                    zone_id="desk_a",
                    log_path=str(log_path),
                ),
            )
        )
    )

    engine.dispatch(
        [
            VisionEvent(
                event_type="zone_focus_started",
                timestamp=1.0,
                description="Desk B entered solo focus",
                metadata={"zone_id": "desk_b"},
            )
        ]
    )

    assert not log_path.exists()


def test_trigger_engine_logs_dispatch_failures(monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    logger = VisionLogger(json_mode=False)
    engine = TriggerEngine(
        TriggerConfig(
            rules=(
                TriggerRule(
                    rule_id="desk-a-webhook",
                    event_type="zone_focus_started",
                    webhook_url="https://example.invalid/hook",
                ),
            )
        ),
        logger=logger,
    )

    monkeypatch.setattr("integrations.engine.urlopen", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    engine.dispatch(
        [
            VisionEvent(
                event_type="zone_focus_started",
                timestamp=1.0,
                description="Desk A entered solo focus",
                metadata={"zone_id": "desk_a"},
            )
        ]
    )

    stderr = capsys.readouterr().err
    assert "trigger_dispatch_failed" in stderr
