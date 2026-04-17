"""Runtime integration publishing helpers."""

from __future__ import annotations

from collections import defaultdict

from common.models import Decision, HistoryRecord, RuntimeMetrics, SessionAnalyticsSummary, VisionEvent
from integrations.dispatcher import IntegrationDispatcher
from integrations.models import IntegrationConfig, IntegrationEnvelope, IntegrationTarget, TriggeredActionRecord
from telemetry.logging import VisionLogger


class IntegrationPublisher:
    """Publish runtime outputs to configured generic integration targets."""

    def __init__(
        self,
        config: IntegrationConfig,
        *,
        dispatcher: IntegrationDispatcher | None = None,
        source_mode: str,
        profile_id: str | None = None,
        logger: VisionLogger | None = None,
    ) -> None:
        self.config = config
        self.source_mode = source_mode
        self.profile_id = profile_id
        self.dispatcher = dispatcher or IntegrationDispatcher(logger=logger)
        self._last_status_dispatch_at: dict[str, float] = {}

    def publish_runtime(
        self,
        *,
        decision: Decision,
        runtime_metrics: RuntimeMetrics,
        history_record: HistoryRecord,
        events: tuple[VisionEvent, ...],
        trigger_records: tuple[TriggeredActionRecord, ...],
    ) -> tuple:
        records = []
        records.extend(self._publish_events(decision, runtime_metrics, events))
        records.extend(self._publish_triggers(decision, runtime_metrics, trigger_records))
        records.extend(self._publish_status(decision, runtime_metrics, history_record))
        return tuple(records)

    def publish_session_summary(self, summary: SessionAnalyticsSummary) -> tuple:
        targets = tuple(target for target in self.config.targets if target.enabled and target.source == "session_summary")
        if not targets:
            return ()
        timestamp = summary.ended_at if summary.ended_at is not None else 0.0
        envelope = IntegrationEnvelope(
            source="session_summary",
            timestamp=timestamp,
            source_mode=self.source_mode,
            scene_label=summary.dominant_scene_label,
            confidence=None,
            profile_id=self.profile_id,
            metrics={
                "duration_seconds": summary.duration_seconds,
                "fps": summary.fps,
                "average_inference_ms": summary.average_inference_ms,
                "decision_switch_rate": summary.decision_switch_rate,
                "average_stability_score": summary.average_stability_score,
            },
            payload=summary.to_dict(),
        )
        return self.dispatcher.dispatch_many(targets, envelope)

    def _publish_events(
        self,
        decision: Decision,
        runtime_metrics: RuntimeMetrics,
        events: tuple[VisionEvent, ...],
    ) -> tuple:
        targets = tuple(target for target in self.config.targets if target.enabled and target.source == "event")
        if not targets or not events:
            return ()

        records = []
        for event in events:
            matching_targets = tuple(
                target for target in targets if not target.event_types or event.event_type in target.event_types
            )
            if not matching_targets:
                continue
            envelope = IntegrationEnvelope(
                source="event",
                timestamp=event.timestamp,
                source_mode=self.source_mode,
                scene_label=decision.label.value,
                confidence=decision.confidence,
                profile_id=self.profile_id,
                metrics=_metrics_payload(decision, runtime_metrics),
                risk_flags=tuple(decision.risk_flags),
                payload=event.to_dict(),
            )
            records.extend(self.dispatcher.dispatch_many(matching_targets, envelope))
        return tuple(records)

    def _publish_triggers(
        self,
        decision: Decision,
        runtime_metrics: RuntimeMetrics,
        trigger_records: tuple[TriggeredActionRecord, ...],
    ) -> tuple:
        targets = tuple(target for target in self.config.targets if target.enabled and target.source == "trigger")
        if not targets or not trigger_records:
            return ()

        grouped: dict[tuple[str, float], list[TriggeredActionRecord]] = defaultdict(list)
        for record in trigger_records:
            grouped[(record.trigger_id, record.timestamp)].append(record)

        records = []
        for (trigger_id, timestamp), grouped_records in grouped.items():
            matching_targets = tuple(
                target for target in targets if not target.trigger_ids or trigger_id in target.trigger_ids
            )
            if not matching_targets:
                continue
            first = grouped_records[0]
            envelope_payload = dict(first.payload)
            envelope_payload["trigger_id"] = trigger_id
            envelope_payload["action_types"] = [record.action_type for record in grouped_records]
            envelope_payload["failed_actions"] = [record.action_type for record in grouped_records if not record.success]
            envelope = IntegrationEnvelope(
                source="trigger",
                timestamp=timestamp,
                source_mode=self.source_mode,
                scene_label=decision.label.value,
                confidence=decision.confidence,
                profile_id=self.profile_id,
                metrics=_metrics_payload(decision, runtime_metrics),
                risk_flags=tuple(decision.risk_flags),
                payload=envelope_payload,
            )
            records.extend(self.dispatcher.dispatch_many(matching_targets, envelope))
        return tuple(records)

    def _publish_status(
        self,
        decision: Decision,
        runtime_metrics: RuntimeMetrics,
        history_record: HistoryRecord,
    ) -> tuple:
        targets = tuple(target for target in self.config.targets if target.enabled and target.source == "status")
        if not targets:
            return ()

        records = []
        for target in targets:
            interval_seconds = target.interval_seconds or 0.0
            last_sent_at = self._last_status_dispatch_at.get(target.integration_id)
            if last_sent_at is not None and (history_record.timestamp - last_sent_at) < interval_seconds:
                continue
            envelope = IntegrationEnvelope(
                source="status",
                timestamp=history_record.timestamp,
                source_mode=self.source_mode,
                scene_label=decision.label.value,
                confidence=decision.confidence,
                profile_id=self.profile_id,
                metrics=_metrics_payload(decision, runtime_metrics),
                risk_flags=tuple(decision.risk_flags),
                payload={
                    "frame_index": history_record.frame_index,
                    "scene_label": history_record.scene_label,
                    "confidence": history_record.confidence,
                    "action": history_record.action,
                    "event_types": list(history_record.event_types),
                    "trigger_ids": list(history_record.trigger_ids),
                    "zone_labels": history_record.zone_labels,
                    "runtime_metrics": runtime_metrics.to_dict(),
                },
            )
            records.extend(self.dispatcher.dispatch_many((target,), envelope))
            self._last_status_dispatch_at[target.integration_id] = history_record.timestamp
        return tuple(records)


def _metrics_payload(decision: Decision, runtime_metrics: RuntimeMetrics) -> dict[str, object]:
    return {
        "focus_score": decision.scene_metrics.focus_score,
        "distraction_score": decision.scene_metrics.distraction_score,
        "collaboration_score": decision.scene_metrics.collaboration_score,
        "stability_score": decision.scene_metrics.stability_score,
        "focus_duration_seconds": decision.scene_metrics.focus_duration_seconds,
        "decision_switch_rate": decision.scene_metrics.decision_switch_rate,
        "fps": runtime_metrics.fps,
        "average_inference_ms": runtime_metrics.average_inference_ms,
        "dropped_frames": runtime_metrics.dropped_frames,
    }
