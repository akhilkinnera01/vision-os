"""Structured trigger action dispatch helpers."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

from integrations.models import TriggerRule, TriggeredActionRecord
from integrations.mqtt import publish_json
from telemetry.logging import VisionLogger


class TriggerDispatcher:
    """Dispatch trigger actions and return structured action records."""

    def __init__(self, logger: VisionLogger | None = None) -> None:
        self.logger = logger

    def dispatch(
        self,
        rule: TriggerRule,
        *,
        timestamp: float,
        payload: dict[str, object],
    ) -> tuple[TriggeredActionRecord, ...]:
        payload_bytes = json.dumps(payload).encode("utf-8")
        records: list[TriggeredActionRecord] = []
        for action in rule.actions:
            if action.action_type == "stdout":
                print(json.dumps(payload))
                records.append(
                    TriggeredActionRecord(
                        trigger_id=rule.rule_id,
                        action_type="stdout",
                        timestamp=timestamp,
                        target=None,
                        payload=payload,
                        success=True,
                    )
                )
                continue
            if action.action_type == "file_append":
                error = self._write_log(action.target or "", payload_bytes)
                records.append(
                    TriggeredActionRecord(
                        trigger_id=rule.rule_id,
                        action_type="file_append",
                        timestamp=timestamp,
                        target=action.target,
                        payload=payload,
                        success=error is None,
                        error=error,
                    )
                )
                continue
            if action.action_type == "log":
                if self.logger is not None:
                    self.logger.log(action.target or "trigger_fired", trigger_id=rule.rule_id, payload=payload)
                records.append(
                    TriggeredActionRecord(
                        trigger_id=rule.rule_id,
                        action_type="log",
                        timestamp=timestamp,
                        target=action.target,
                        payload=payload,
                        success=True,
                    )
                )
                continue
            if action.action_type == "webhook":
                error = self._post_webhook(action.target or "", action.method, payload_bytes)
                records.append(
                    TriggeredActionRecord(
                        trigger_id=rule.rule_id,
                        action_type="webhook",
                        timestamp=timestamp,
                        target=action.target,
                        payload=payload,
                        success=error is None,
                        error=error,
                    )
                )
                continue
            if action.action_type == "mqtt_publish":
                topic = action.mqtt_topic or action.target or ""
                error = self._publish_mqtt(action.mqtt_host or "", action.mqtt_port, topic, payload_bytes)
                records.append(
                    TriggeredActionRecord(
                        trigger_id=rule.rule_id,
                        action_type="mqtt_publish",
                        timestamp=timestamp,
                        target=topic,
                        payload=payload,
                        success=error is None,
                        error=error,
                    )
                )
                continue
            raise ValueError(f"Unsupported trigger action type: {action.action_type}")
        return tuple(records)

    def _write_log(self, path: str, payload: bytes) -> str | None:
        target = Path(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("ab") as handle:
                handle.write(payload + b"\n")
            return None
        except OSError as exc:
            self._log_failure("file_append", path, exc)
            return str(exc)

    def _post_webhook(self, url: str, method: str, payload: bytes) -> str | None:
        request = Request(url=url, data=payload, headers={"Content-Type": "application/json"}, method=method)
        try:
            with urlopen(request, timeout=2.0):
                return None
        except Exception as exc:  # pragma: no cover - exercised via tests with mocking
            self._log_failure("webhook", url, exc)
            return str(exc)

    def _publish_mqtt(self, host: str, port: int, topic: str, payload: bytes) -> str | None:
        try:
            publish_json(host, port, topic, payload)
            return None
        except Exception as exc:  # pragma: no cover - exercised via tests with mocking
            self._log_failure("mqtt", f"{host}:{port}/{topic}", exc)
            return str(exc)

    def _log_failure(self, sink: str, target: str, exc: Exception) -> None:
        if self.logger is not None:
            self.logger.log("trigger_dispatch_failed", sink=sink, target=target, error=str(exc))
