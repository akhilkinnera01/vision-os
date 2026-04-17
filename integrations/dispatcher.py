"""Structured dispatch helpers for triggers and generic integrations."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

from integrations.models import DispatchRecord, IntegrationEnvelope, IntegrationTarget, TriggerRule, TriggeredActionRecord
from integrations.mqtt import publish_json
from telemetry.logging import VisionLogger


class IntegrationDispatcher:
    """Dispatch structured integration envelopes to configured targets."""

    def __init__(self, logger: VisionLogger | None = None) -> None:
        self.logger = logger

    def dispatch_many(
        self,
        targets: tuple[IntegrationTarget, ...],
        envelope: IntegrationEnvelope,
    ) -> tuple[DispatchRecord, ...]:
        payload = envelope.to_dict()
        payload_bytes = json.dumps(payload).encode("utf-8")
        records: list[DispatchRecord] = []
        for target in targets:
            if not target.enabled:
                continue
            if target.target_type == "stdout":
                print(json.dumps(payload))
                records.append(
                    DispatchRecord(
                        integration_id=target.integration_id,
                        target_type=target.target_type,
                        source=envelope.source,
                        timestamp=envelope.timestamp,
                        target=target.target,
                        payload=payload,
                        success=True,
                    )
                )
                continue
            if target.target_type == "file_append":
                error = _write_jsonl(target.target or "", payload_bytes, logger=self.logger, failure_event="integration_dispatch_failed")
                records.append(
                    DispatchRecord(
                        integration_id=target.integration_id,
                        target_type=target.target_type,
                        source=envelope.source,
                        timestamp=envelope.timestamp,
                        target=target.target,
                        payload=payload,
                        success=error is None,
                        error=error,
                    )
                )
                continue
            if target.target_type == "log":
                if self.logger is not None:
                    self.logger.log(
                        target.target or "integration_dispatch",
                        integration_id=target.integration_id,
                        source=envelope.source,
                        payload=payload,
                    )
                records.append(
                    DispatchRecord(
                        integration_id=target.integration_id,
                        target_type=target.target_type,
                        source=envelope.source,
                        timestamp=envelope.timestamp,
                        target=target.target,
                        payload=payload,
                        success=True,
                    )
                )
                continue
            if target.target_type == "webhook":
                error = _post_webhook(
                    target.target or "",
                    target.method,
                    payload_bytes,
                    logger=self.logger,
                    failure_event="integration_dispatch_failed",
                )
                records.append(
                    DispatchRecord(
                        integration_id=target.integration_id,
                        target_type=target.target_type,
                        source=envelope.source,
                        timestamp=envelope.timestamp,
                        target=target.target,
                        payload=payload,
                        success=error is None,
                        error=error,
                    )
                )
                continue
            if target.target_type == "mqtt_publish":
                topic = target.mqtt_topic or target.target or ""
                error = _publish_mqtt(
                    target.mqtt_host or "",
                    target.mqtt_port,
                    topic,
                    payload_bytes,
                    logger=self.logger,
                    failure_event="integration_dispatch_failed",
                )
                records.append(
                    DispatchRecord(
                        integration_id=target.integration_id,
                        target_type=target.target_type,
                        source=envelope.source,
                        timestamp=envelope.timestamp,
                        target=topic,
                        payload=payload,
                        success=error is None,
                        error=error,
                    )
                )
                continue
            raise ValueError(f"Unsupported integration target type: {target.target_type}")
        return tuple(records)


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
                error = _write_jsonl(
                    action.target or "",
                    payload_bytes,
                    logger=self.logger,
                    failure_event="trigger_dispatch_failed",
                )
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
                error = _post_webhook(
                    action.target or "",
                    action.method,
                    payload_bytes,
                    logger=self.logger,
                    failure_event="trigger_dispatch_failed",
                )
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
                error = _publish_mqtt(
                    action.mqtt_host or "",
                    action.mqtt_port,
                    topic,
                    payload_bytes,
                    logger=self.logger,
                    failure_event="trigger_dispatch_failed",
                )
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


def _write_jsonl(path: str, payload: bytes, *, logger: VisionLogger | None, failure_event: str) -> str | None:
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("ab") as handle:
            handle.write(payload + b"\n")
        return None
    except OSError as exc:
        _log_failure(logger, failure_event, "file_append", path, exc)
        return str(exc)


def _post_webhook(
    url: str,
    method: str,
    payload: bytes,
    *,
    logger: VisionLogger | None,
    failure_event: str,
) -> str | None:
    request = Request(url=url, data=payload, headers={"Content-Type": "application/json"}, method=method)
    try:
        with urlopen(request, timeout=2.0):
            return None
    except Exception as exc:  # pragma: no cover - exercised via tests with mocking
        _log_failure(logger, failure_event, "webhook", url, exc)
        return str(exc)


def _publish_mqtt(
    host: str,
    port: int,
    topic: str,
    payload: bytes,
    *,
    logger: VisionLogger | None,
    failure_event: str,
) -> str | None:
    try:
        publish_json(host, port, topic, payload)
        return None
    except Exception as exc:  # pragma: no cover - exercised via tests with mocking
        _log_failure(logger, failure_event, "mqtt", f"{host}:{port}/{topic}", exc)
        return str(exc)


def _log_failure(
    logger: VisionLogger | None,
    failure_event: str,
    sink: str,
    target: str,
    exc: Exception,
) -> None:
    if logger is not None:
        logger.log(failure_event, sink=sink, target=target, error=str(exc))
