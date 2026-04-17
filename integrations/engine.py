"""Dispatch matched events to log, webhook, and MQTT outputs."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

from common.models import VisionEvent
from integrations.config import TriggerConfig, TriggerRule
from integrations.mqtt import publish_json
from telemetry.logging import VisionLogger


class TriggerEngine:
    """Dispatch trigger outputs while keeping runtime failures non-fatal."""

    def __init__(self, config: TriggerConfig, logger: VisionLogger | None = None) -> None:
        self.config = config
        self.logger = logger

    def dispatch(self, events: list[VisionEvent]) -> None:
        for event in events:
            for rule in self.config.rules:
                if not self._matches(rule, event):
                    continue
                payload = json.dumps(self._event_payload(rule, event)).encode("utf-8")
                self._run_outputs(rule, payload)

    def _matches(self, rule: TriggerRule, event: VisionEvent) -> bool:
        if event.event_type != rule.event_type:
            return False
        if rule.zone_id is not None and event.metadata.get("zone_id") != rule.zone_id:
            return False
        return True

    def _event_payload(self, rule: TriggerRule, event: VisionEvent) -> dict[str, object]:
        return {
            "trigger_id": rule.rule_id,
            "event": event.to_dict(),
        }

    def _run_outputs(self, rule: TriggerRule, payload: bytes) -> None:
        if rule.log_path:
            self._write_log(rule.log_path, payload)
        if rule.webhook_url:
            self._post_webhook(rule.webhook_url, payload)
        if rule.mqtt_host and rule.mqtt_topic:
            self._publish_mqtt(rule.mqtt_host, rule.mqtt_port, rule.mqtt_topic, payload)

    def _write_log(self, path: str, payload: bytes) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("ab") as handle:
            handle.write(payload + b"\n")

    def _post_webhook(self, url: str, payload: bytes) -> None:
        request = Request(url=url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=2.0):
                pass
        except Exception as exc:  # pragma: no cover - exercised via tests with mocking
            self._log_failure("webhook", url, exc)

    def _publish_mqtt(self, host: str, port: int, topic: str, payload: bytes) -> None:
        try:
            publish_json(host, port, topic, payload)
        except Exception as exc:  # pragma: no cover - exercised via tests with mocking
            self._log_failure("mqtt", f"{host}:{port}/{topic}", exc)

    def _log_failure(self, sink: str, target: str, exc: Exception) -> None:
        if self.logger is not None:
            self.logger.log("trigger_dispatch_failed", sink=sink, target=target, error=str(exc))
