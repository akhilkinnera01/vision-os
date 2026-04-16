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
    RuntimeMetrics,
    VisionEvent,
)
from common.policy import VisionPolicy
from context.rules import ContextRulesEngine
from decision.engine import DecisionEngine
from events.emitter import EventEmitter
from explain.explain import ExplanationEngine
from features.builder import FeatureBuilder
from perception.detector import YOLODetector
from runtime.benchmark import BenchmarkTracker
from runtime.io import FramePacket
from state.actor_store import ActorStore
from state.memory import TemporalMemory
from telemetry.timers import StageTimer
from tracking.tracker import DetectionTracker


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


class VisionPipeline:
    """Process packets through tracking, reasoning, events, and telemetry."""

    def __init__(
        self,
        config: VisionOSConfig,
        policy: VisionPolicy,
        detector: YOLODetector | None = None,
        benchmark_tracker: BenchmarkTracker | None = None,
    ) -> None:
        self.config = config
        self.policy = policy
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
            )

        with timer.measure("explain"):
            explanation = self.explanation_engine.explain(
                decision,
                scene_context,
                features,
                temporal_state,
                self.benchmark_tracker.snapshot(),
                events=events,
            )

        inference_ms = (time.perf_counter() - start) * 1000.0
        runtime_metrics = self.benchmark_tracker.record_inference(
            packet.timestamp,
            inference_ms,
            decision.label,
            stage_timings=timer.snapshot(),
            scene_stability_score=temporal_state.metrics.stability_score,
        )
        return InferenceOutput(
            frame_index=packet.frame_index,
            detections=detections,
            decision=decision,
            explanation=explanation,
            runtime_metrics=runtime_metrics,
            events=events,
            actor_frame_state=actor_frame_state,
        )
