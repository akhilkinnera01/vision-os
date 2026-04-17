"""Dispatch matched events to log, webhook, and MQTT outputs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from common.models import ContextLabel, Decision, SceneMetrics, TemporalState, VisionEvent
from integrations.config import TriggerConfig, TriggerRule
from integrations.models import TriggerRuleState, TriggerSnapshot, TriggeredActionRecord
from integrations.mqtt import publish_json
from telemetry.logging import VisionLogger


class TriggerEngine:
    """Dispatch trigger outputs while keeping runtime failures non-fatal."""

    def __init__(self, config: TriggerConfig, logger: VisionLogger | None = None) -> None:
        self.config = config
        self.logger = logger
        self._rule_states: dict[str, TriggerRuleState] = {
            rule.rule_id: TriggerRuleState() for rule in self.config.rules
        }

    def evaluate(self, snapshot: TriggerSnapshot) -> tuple[TriggeredActionRecord, ...]:
        records: list[TriggeredActionRecord] = []
        for rule in self.config.rules:
            if not rule.enabled or rule.condition is None:
                continue
            state = self._rule_states.setdefault(rule.rule_id, TriggerRuleState())
            matched, matching_event = self._condition_result(rule, snapshot)
            if rule.condition.source.startswith("event."):
                if matched and self._cooldown_ready(rule, state, snapshot.timestamp):
                    records.extend(self._run_actions(rule, snapshot, matching_event))
                    state.last_fired_at = snapshot.timestamp
                    state.fire_count += 1
                continue

            if matched:
                if not state.condition_was_true:
                    state.satisfied_since = snapshot.timestamp
                    state.condition_was_true = True
                satisfied_since = state.satisfied_since if state.satisfied_since is not None else snapshot.timestamp
                duration = snapshot.timestamp - satisfied_since
                duration_ok = duration >= rule.condition.min_duration_seconds
                if (
                    state.armed
                    and not state.fired_in_current_streak
                    and duration_ok
                    and self._cooldown_ready(rule, state, snapshot.timestamp)
                ):
                    records.extend(self._run_actions(rule, snapshot, matching_event))
                    state.last_fired_at = snapshot.timestamp
                    state.fire_count += 1
                    state.fired_in_current_streak = True
                    if not rule.rearm_on_clear:
                        state.armed = False
                continue

            state.condition_was_true = False
            state.satisfied_since = None
            state.fired_in_current_streak = False
            if rule.rearm_on_clear:
                state.armed = True

        return tuple(records)

    def dispatch(self, events: list[VisionEvent]) -> None:
        snapshot = TriggerSnapshot(
            timestamp=events[0].timestamp if events else 0.0,
            decision=Decision(
                label=ContextLabel.CASUAL_USE,
                confidence=0.0,
                action="observe",
                scene_metrics=SceneMetrics(),
            ),
            temporal_state=TemporalState(),
            events=tuple(events),
            zone_states=(),
        )
        self.evaluate(snapshot)

    def _cooldown_ready(self, rule: TriggerRule, state: TriggerRuleState, timestamp: float) -> bool:
        if state.last_fired_at is None:
            return True
        return (timestamp - state.last_fired_at) >= rule.cooldown_seconds

    def _condition_result(self, rule: TriggerRule, snapshot: TriggerSnapshot) -> tuple[bool, VisionEvent | None]:
        condition = rule.condition
        if condition is None:
            return False, None
        if condition.source == "decision.label":
            actual = snapshot.decision.label.value
            return self._compare(actual, condition.operator, condition.value), None
        if condition.source == "decision.confidence":
            actual = snapshot.decision.confidence
            return self._compare(actual, condition.operator, condition.value), None
        if condition.source.startswith("temporal.metrics."):
            metric_name = condition.source.removeprefix("temporal.metrics.")
            actual = getattr(snapshot.temporal_state.metrics, metric_name)
            return self._compare(actual, condition.operator, condition.value), None
        if condition.source == "event.event_type":
            for event in snapshot.events:
                if not self._compare(event.event_type, condition.operator, condition.value):
                    continue
                if any(event.metadata.get(key) != value for key, value in condition.event_metadata_filters.items()):
                    continue
                return True, event
            return False, None
        raise ValueError(f"Unsupported trigger condition source: {condition.source}")

    def _compare(self, actual: object, operator: str, expected: object) -> bool:
        if operator == "equals":
            return actual == expected
        if operator == "not_equals":
            return actual != expected
        if operator == "gte":
            return float(actual) >= float(expected)
        if operator == "gt":
            return float(actual) > float(expected)
        if operator == "lte":
            return float(actual) <= float(expected)
        if operator == "lt":
            return float(actual) < float(expected)
        raise ValueError(f"Unsupported trigger operator: {operator}")

    def _event_payload(self, rule: TriggerRule, snapshot: TriggerSnapshot, event: VisionEvent | None) -> dict[str, object]:
        return {
            "trigger_id": rule.rule_id,
            "timestamp": snapshot.timestamp,
            "label": snapshot.decision.label.value,
            "confidence": snapshot.decision.confidence,
            "metrics": {
                "focus": snapshot.decision.scene_metrics.focus_score,
                "distraction": snapshot.decision.scene_metrics.distraction_score,
                "collaboration": snapshot.decision.scene_metrics.collaboration_score,
                "stability": snapshot.decision.scene_metrics.stability_score,
            },
            "event": None if event is None else event.to_dict(),
        }

    def _run_actions(
        self,
        rule: TriggerRule,
        snapshot: TriggerSnapshot,
        event: VisionEvent | None,
    ) -> list[TriggeredActionRecord]:
        payload_dict = self._event_payload(rule, snapshot, event)
        payload = json.dumps(payload_dict).encode("utf-8")
        records: list[TriggeredActionRecord] = []
        for action in rule.actions:
            if action.action_type == "stdout":
                print(json.dumps(payload_dict))
                records.append(
                    TriggeredActionRecord(
                        trigger_id=rule.rule_id,
                        action_type="stdout",
                        timestamp=snapshot.timestamp,
                        target=None,
                        payload=payload_dict,
                        success=True,
                    )
                )
                continue
            if action.action_type == "file_append":
                self._write_log(action.target or "", payload)
                records.append(
                    TriggeredActionRecord(
                        trigger_id=rule.rule_id,
                        action_type="file_append",
                        timestamp=snapshot.timestamp,
                        target=action.target,
                        payload=payload_dict,
                        success=True,
                    )
                )
                continue
            if action.action_type == "log":
                if self.logger is not None:
                    self.logger.log(action.target or "trigger_fired", trigger_id=rule.rule_id, payload=payload_dict)
                records.append(
                    TriggeredActionRecord(
                        trigger_id=rule.rule_id,
                        action_type="log",
                        timestamp=snapshot.timestamp,
                        target=action.target,
                        payload=payload_dict,
                        success=True,
                    )
                )
                continue
            if action.action_type == "webhook":
                error = self._post_webhook(action.target or "", payload)
                records.append(
                    TriggeredActionRecord(
                        trigger_id=rule.rule_id,
                        action_type="webhook",
                        timestamp=snapshot.timestamp,
                        target=action.target,
                        payload=payload_dict,
                        success=error is None,
                        error=error,
                    )
                )
                continue
            if action.action_type == "mqtt_publish":
                topic = action.mqtt_topic or action.target or ""
                error = self._publish_mqtt(action.mqtt_host or "", action.mqtt_port, topic, payload)
                records.append(
                    TriggeredActionRecord(
                        trigger_id=rule.rule_id,
                        action_type="mqtt_publish",
                        timestamp=snapshot.timestamp,
                        target=topic,
                        payload=payload_dict,
                        success=error is None,
                        error=error,
                    )
                )
                continue
            raise ValueError(f"Unsupported trigger action type: {action.action_type}")
        return records

    def _write_log(self, path: str, payload: bytes) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("ab") as handle:
            handle.write(payload + b"\n")

    def _post_webhook(self, url: str, payload: bytes) -> str | None:
        request = Request(url=url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
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
