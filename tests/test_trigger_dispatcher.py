"""Tests for structured trigger action dispatch."""

from __future__ import annotations

import json
from pathlib import Path

from integrations import TriggerAction, TriggerRule
from integrations.dispatcher import TriggerDispatcher
from telemetry.logging import VisionLogger


def test_dispatcher_returns_structured_records_for_stdout_and_file_append(
    tmp_path: Path,
    capsys,
) -> None:
    rule = TriggerRule(
        rule_id="focus-session",
        actions=(
            TriggerAction(action_type="stdout"),
            TriggerAction(action_type="file_append", target=str(tmp_path / "events.jsonl")),
        ),
    )
    dispatcher = TriggerDispatcher()
    payload = {"trigger_id": "focus-session", "label": "Focused Work"}

    records = dispatcher.dispatch(rule, timestamp=12.0, payload=payload)

    stdout = capsys.readouterr().out
    assert json.loads(stdout.strip()) == payload
    assert [record.action_type for record in records] == ["stdout", "file_append"]
    assert all(record.success for record in records)
    assert (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip()


def test_dispatcher_logs_failure_and_continues_to_other_actions(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    rule = TriggerRule(
        rule_id="focus-session",
        actions=(
            TriggerAction(action_type="webhook", target="https://example.invalid/hook"),
            TriggerAction(action_type="file_append", target=str(tmp_path / "events.jsonl")),
        ),
    )
    dispatcher = TriggerDispatcher(logger=VisionLogger(json_mode=False))
    payload = {"trigger_id": "focus-session", "label": "Focused Work"}

    monkeypatch.setattr(
        "integrations.dispatcher.urlopen",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    records = dispatcher.dispatch(rule, timestamp=12.0, payload=payload)

    stderr = capsys.readouterr().err
    assert "trigger_dispatch_failed" in stderr
    assert records[0].success is False
    assert records[0].error == "boom"
    assert records[1].success is True
    assert (tmp_path / "events.jsonl").is_file()


def test_dispatcher_uses_configured_webhook_method(monkeypatch) -> None:
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

    rule = TriggerRule(
        rule_id="focus-session",
        actions=(TriggerAction(action_type="webhook", target="https://example.invalid/hook", method="PATCH"),),
    )
    dispatcher = TriggerDispatcher()

    monkeypatch.setattr("integrations.dispatcher.urlopen", _fake_urlopen)

    records = dispatcher.dispatch(rule, timestamp=5.0, payload={"trigger_id": "focus-session"})

    assert len(records) == 1
    assert records[0].action_type == "webhook"
    assert records[0].success is True
    assert captured_request is not None
    assert captured_request.get_method() == "PATCH"


def test_dispatcher_records_file_append_failures_without_raising(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    rule = TriggerRule(
        rule_id="focus-session",
        actions=(TriggerAction(action_type="file_append", target=str(tmp_path / "events.jsonl")),),
    )
    dispatcher = TriggerDispatcher(logger=VisionLogger(json_mode=False))

    def _raise_oserror(self, *args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "open", _raise_oserror)

    records = dispatcher.dispatch(rule, timestamp=9.0, payload={"trigger_id": "focus-session"})

    stderr = capsys.readouterr().err
    assert "trigger_dispatch_failed" in stderr
    assert len(records) == 1
    assert records[0].action_type == "file_append"
    assert records[0].success is False
    assert records[0].error == "disk full"


def test_dispatcher_supports_structured_log_actions(capsys) -> None:
    rule = TriggerRule(
        rule_id="focus-session",
        actions=(TriggerAction(action_type="log", target="trigger_fired"),),
    )
    dispatcher = TriggerDispatcher(logger=VisionLogger(json_mode=False))
    payload = {"trigger_id": "focus-session", "label": "Focused Work"}

    records = dispatcher.dispatch(rule, timestamp=8.0, payload=payload)

    stderr = capsys.readouterr().err
    assert "trigger_fired" in stderr
    assert len(records) == 1
    assert records[0].action_type == "log"
    assert records[0].success is True
