"""Tests for generic integration dispatch."""

from __future__ import annotations

import json
from pathlib import Path

from integrations import IntegrationTarget
from integrations.dispatcher import IntegrationDispatcher
from integrations.models import IntegrationEnvelope
from telemetry.logging import VisionLogger


def test_integration_dispatcher_writes_stdout_and_file_append(
    tmp_path: Path,
    capsys,
) -> None:
    dispatcher = IntegrationDispatcher()
    envelope = IntegrationEnvelope(
        source="event",
        timestamp=12.0,
        source_mode="video",
        scene_label="Focused Work",
        confidence=0.91,
        payload={"event_type": "distraction_started"},
    )

    records = dispatcher.dispatch_many(
        (
            IntegrationTarget(integration_id="event-stdout", target_type="stdout", source="event"),
            IntegrationTarget(
                integration_id="event-log",
                target_type="file_append",
                source="event",
                target=str(tmp_path / "events.jsonl"),
            ),
        ),
        envelope,
    )

    stdout = capsys.readouterr().out
    assert json.loads(stdout.strip())["payload"]["event_type"] == "distraction_started"
    assert [record.integration_id for record in records] == ["event-stdout", "event-log"]
    assert all(record.success for record in records)
    written = json.loads((tmp_path / "events.jsonl").read_text(encoding="utf-8").strip())
    assert written["source"] == "event"
    assert written["payload"]["event_type"] == "distraction_started"


def test_integration_dispatcher_uses_configured_webhook_method(monkeypatch) -> None:
    captured_request = None

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    def _fake_urlopen(request, timeout: float):
        nonlocal captured_request
        captured_request = request
        assert timeout == 2.0
        return _Response()

    dispatcher = IntegrationDispatcher()
    envelope = IntegrationEnvelope(
        source="status",
        timestamp=3.0,
        source_mode="webcam",
        scene_label="Casual Use",
        confidence=0.5,
        payload={"label": "Casual Use"},
    )
    target = IntegrationTarget(
        integration_id="status-hook",
        target_type="webhook",
        source="status",
        target="https://example.invalid/status",
        method="PATCH",
        interval_seconds=5.0,
    )

    monkeypatch.setattr("integrations.dispatcher.urlopen", _fake_urlopen)

    records = dispatcher.dispatch_many((target,), envelope)

    assert len(records) == 1
    assert records[0].target_type == "webhook"
    assert records[0].success is True
    assert captured_request is not None
    assert captured_request.get_method() == "PATCH"


def test_integration_dispatcher_logs_mqtt_failures_without_raising(
    monkeypatch,
    capsys,
) -> None:
    dispatcher = IntegrationDispatcher(logger=VisionLogger(json_mode=False))
    envelope = IntegrationEnvelope(
        source="session_summary",
        timestamp=30.0,
        source_mode="replay",
        scene_label="Focused Work",
        confidence=0.88,
        payload={"dominant_scene_label": "Focused Work"},
    )
    target = IntegrationTarget(
        integration_id="summary-mqtt",
        target_type="mqtt_publish",
        source="session_summary",
        mqtt_host="127.0.0.1",
        mqtt_port=1883,
        mqtt_topic="visionos/summary",
        target="visionos/summary",
    )

    monkeypatch.setattr(
        "integrations.dispatcher.publish_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("mqtt down")),
    )

    records = dispatcher.dispatch_many((target,), envelope)

    stderr = capsys.readouterr().err
    assert "integration_dispatch_failed" in stderr
    assert len(records) == 1
    assert records[0].success is False
    assert records[0].error == "mqtt down"
