"""Shared packet-processing pipeline for live, video, and replay modes."""

from __future__ import annotations

import time
from dataclasses import dataclass

from common.config import VisionOSConfig
from common.models import (
    ActorFrameState,
    Decision,
    Detection,
    Explanation,
    HistoryRecord,
    RuntimeMetrics,
    VisionEvent,
)
from common.policy import VisionPolicy
from context.rules import ContextRulesEngine
from decision.engine import DecisionEngine
from events.emitter import EventEmitter
from explain.explain import ExplanationEngine
from features.builder import FeatureBuilder
from integrations import TriggerConfig, TriggerEngine, TriggeredActionRecord
from integrations.models import TriggerSnapshot
from perception.detector import YOLODetector
from runtime.benchmark import BenchmarkTracker
from runtime.io import FramePacket
from state.actor_store import ActorStore
from state.memory import TemporalMemory
from telemetry.timers import StageTimer
from tracking.tracker import DetectionTracker
from zones import (
    Zone,
    ZoneAssigner,
    ZoneDecisionEngine,
    ZoneFeatureBuilder,
    ZoneRulesEngine,
    ZoneRuntimeState,
    ZoneTemporalMemory,
)


@dataclass(slots=True)
class InferenceOutput:
    """Latest end-to-end inference result for a frame packet."""

    frame_index: int
    detections: list[Detection]
    decision: Decision
    explanation: Explanation
    runtime_metrics: RuntimeMetrics
    events: list[VisionEvent]
    actor_frame_state: ActorFrameState
    history_record: HistoryRecord
    zone_states: tuple[ZoneRuntimeState, ...] = ()
    trigger_records: tuple[TriggeredActionRecord, ...] = ()


class VisionPipeline:
    """Process packets through tracking, reasoning, events, and telemetry."""

    def __init__(
        self,
        config: VisionOSConfig,
        policy: VisionPolicy,
        zones: tuple[Zone, ...] = (),
        trigger_config: TriggerConfig | None = None,
        detector: YOLODetector | None = None,
        benchmark_tracker: BenchmarkTracker | None = None,
    ) -> None:
        self.config = config
        self.policy = policy
        self.zones = zones
        self.detector = detector if detector is not None else None if config.source_mode.value == "replay" else YOLODetector(config)
        self.tracker = DetectionTracker(policy.tracking)
        self.actor_store = ActorStore(policy)
        self.feature_builder = FeatureBuilder(policy.features)
        self.temporal_memory = TemporalMemory(config.temporal_window_seconds, policy.temporal)
        self.context_engine = ContextRulesEngine(policy.decision)
        self.decision_engine = DecisionEngine(policy=policy.decision)
        self.event_emitter = EventEmitter(policy.events)
        self.explanation_engine = ExplanationEngine()
        self.benchmark_tracker = benchmark_tracker or BenchmarkTracker()
        self.trigger_engine = TriggerEngine(trigger_config) if trigger_config is not None else None
        self.zone_assigner = ZoneAssigner() if zones else None
        self.zone_feature_builder = ZoneFeatureBuilder(self.feature_builder) if zones else None
        self.zone_rules_engine = ZoneRulesEngine() if zones else None
        self.zone_decision_engine = ZoneDecisionEngine() if zones else None
        self.zone_temporal_memory = ZoneTemporalMemory(config.temporal_window_seconds) if zones else None

    def process(self, packet: FramePacket) -> InferenceOutput:
        timer = StageTimer()
        start = time.perf_counter()

        with timer.measure("detect"):
            raw_detections = (
                packet.replay_detections
                if packet.replay_detections is not None
                else self.detector.detect(packet.frame) if self.detector else []
            )

        with timer.measure("track"):
            detections = self.tracker.update(packet.timestamp, raw_detections, packet.frame.shape[:2])

        with timer.measure("actor_state"):
            actor_frame_state = self.actor_store.update(packet.timestamp, detections, packet.frame.shape[:2])

        with timer.measure("feature"):
            features = self.feature_builder.build(detections, packet.frame.shape[:2], actor_frame_state)

        zone_states: tuple[ZoneRuntimeState, ...] = ()
        if self.zones and self.zone_assigner and self.zone_feature_builder and self.zone_rules_engine and self.zone_decision_engine and self.zone_temporal_memory:
            with timer.measure("zone_assign"):
                zone_assignments = self.zone_assigner.assign(detections, self.zones)

            with timer.measure("zone_feature"):
                zone_feature_sets = self.zone_feature_builder.build(
                    self.zones,
                    zone_assignments,
                    packet.frame.shape[:2],
                    actor_frame_state,
                )

            with timer.measure("zone_context"):
                provisional_zone_contexts = {
                    feature_set.zone_id: self.zone_rules_engine.infer(feature_set)
                    for feature_set in zone_feature_sets
                }

            with timer.measure("zone_temporal"):
                zone_temporal_states = self.zone_temporal_memory.update(
                    packet.timestamp,
                    zone_feature_sets,
                    provisional_zone_contexts,
                )

            with timer.measure("zone_context_refine"):
                zone_contexts = {
                    feature_set.zone_id: self.zone_rules_engine.infer(
                        feature_set,
                        zone_temporal_states[feature_set.zone_id],
                    )
                    for feature_set in zone_feature_sets
                }

            with timer.measure("zone_decision"):
                zone_lookup = {zone.zone_id: zone for zone in self.zones}
                zone_states = tuple(
                    ZoneRuntimeState(
                        zone_id=feature_set.zone_id,
                        zone_name=feature_set.zone_name,
                        zone_type=feature_set.zone_type,
                        feature_set=feature_set,
                        context=zone_contexts[feature_set.zone_id],
                        decision=self.zone_decision_engine.decide(
                            zone_contexts[feature_set.zone_id],
                            zone_temporal_states[feature_set.zone_id],
                        ),
                        temporal_state=zone_temporal_states[feature_set.zone_id],
                        polygon=zone_lookup[feature_set.zone_id].polygon,
                    )
                    for feature_set in zone_feature_sets
                )

        with timer.measure("context"):
            provisional_context = self.context_engine.infer(features)

        with timer.measure("temporal"):
            temporal_state = self.temporal_memory.update(
                packet.timestamp,
                features,
                provisional_context.label,
                provisional_context.confidence,
            )

        with timer.measure("context_refine"):
            scene_context = self.context_engine.infer(features, temporal_state)

        with timer.measure("decision"):
            decision = self.decision_engine.decide(scene_context, features, temporal_state)

        with timer.measure("event"):
            events = self.event_emitter.update(
                packet.timestamp,
                decision,
                temporal_state,
                actor_frame_state,
                features,
                zone_states=zone_states,
            )

        trigger_records: tuple[TriggeredActionRecord, ...] = ()
        if self.trigger_engine is not None:
            with timer.measure("trigger"):
                trigger_records = self.trigger_engine.evaluate(
                    TriggerSnapshot(
                        timestamp=packet.timestamp,
                        decision=decision,
                        temporal_state=temporal_state,
                        events=tuple(events),
                        zone_states=zone_states,
                    )
                )

        with timer.measure("explain"):
            explanation = self.explanation_engine.explain(
                decision,
                scene_context,
                features,
                temporal_state,
                self.benchmark_tracker.snapshot(),
                events=events,
                trigger_records=trigger_records,
                zone_states=zone_states,
            )

        inference_ms = (time.perf_counter() - start) * 1000.0
        runtime_metrics = self.benchmark_tracker.record_inference(
            packet.timestamp,
            inference_ms,
            decision.label,
            stage_timings=timer.snapshot(),
            scene_stability_score=temporal_state.metrics.stability_score,
        )
        history_record = HistoryRecord(
            frame_index=packet.frame_index,
            timestamp=packet.timestamp,
            scene_label=decision.label.value,
            confidence=decision.confidence,
            action=decision.action,
            risk_flags=tuple(decision.risk_flags),
            focus_score=decision.scene_metrics.focus_score,
            distraction_score=decision.scene_metrics.distraction_score,
            collaboration_score=decision.scene_metrics.collaboration_score,
            stability_score=decision.scene_metrics.stability_score,
            focus_duration_seconds=decision.scene_metrics.focus_duration_seconds,
            decision_switch_rate=decision.scene_metrics.decision_switch_rate,
            average_inference_ms=runtime_metrics.average_inference_ms,
            fps=runtime_metrics.fps,
            dropped_frames=runtime_metrics.dropped_frames,
            event_types=tuple(event.event_type for event in events),
            trigger_ids=tuple(record.trigger_id for record in trigger_records),
            zone_labels={zone_state.zone_id: zone_state.context.label.value for zone_state in zone_states},
            stage_timings=runtime_metrics.stage_timings,
        )
        return InferenceOutput(
            frame_index=packet.frame_index,
            detections=detections,
            decision=decision,
            explanation=explanation,
            runtime_metrics=runtime_metrics,
            events=events,
            actor_frame_state=actor_frame_state,
            history_record=history_record,
            zone_states=zone_states,
            trigger_records=trigger_records,
        )
