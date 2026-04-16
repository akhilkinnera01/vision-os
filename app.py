"""Entry point for the Vision OS real-time webcam pipeline."""

from __future__ import annotations

import argparse
import queue
import sys
import threading
import time
from dataclasses import dataclass

import cv2

from common.config import VisionOSConfig
from common.models import (
    Decision,
    Detection,
    Explanation,
    OverlayMode,
    RuntimeMetrics,
    SourceMode,
)
from context.rules import ContextRulesEngine
from decision.engine import DecisionEngine
from explain.explain import ExplanationEngine
from features.builder import FeatureBuilder
from perception.detector import YOLODetector
from runtime.benchmark import BenchmarkTracker
from runtime.io import FramePacket, ReplayFrameSource, ReplayRecorder, VideoFrameSource, WebcamFrameSource
from state.memory import TemporalMemory
from ui.renderer import FrameRenderer


@dataclass(slots=True)
class InferenceOutput:
    """Bundle the latest inference result for the rendering loop."""

    frame_index: int
    detections: list[Detection]
    decision: Decision
    explanation: Explanation
    runtime_metrics: RuntimeMetrics


def parse_args() -> VisionOSConfig:
    """Parse CLI arguments into a runtime config object."""
    parser = argparse.ArgumentParser(description="Run Vision OS on a webcam, video, or replay feed.")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index.")
    parser.add_argument("--source", choices=[mode.value for mode in SourceMode], default="webcam")
    parser.add_argument("--input", help="Path to a video file or replay artifact.")
    parser.add_argument("--model", default="yolov8n.pt", help="YOLO weights path or name.")
    parser.add_argument("--conf", type=float, default=0.35, help="Confidence threshold.")
    parser.add_argument("--imgsz", type=int, default=640, help="YOLO inference size.")
    parser.add_argument(
        "--device",
        default=None,
        help="Optional inference device such as cpu, mps, or 0 for CUDA.",
    )
    parser.add_argument(
        "--max-detections",
        type=int,
        default=25,
        help="Cap detections per frame to keep overlays readable.",
    )
    parser.add_argument("--record", help="Optional path to save replayable detections as JSONL.")
    parser.add_argument("--benchmark-output", help="Optional path to write benchmark metrics as JSON.")
    parser.add_argument(
        "--overlay-mode",
        choices=[mode.value for mode in OverlayMode],
        default=OverlayMode.COMPACT.value,
        help="Choose compact or debug overlay rendering.",
    )
    parser.add_argument(
        "--temporal-window",
        type=float,
        default=8.0,
        help="Rolling temporal window in seconds for scene memory.",
    )
    parser.add_argument("--max-frames", type=int, default=None, help="Stop after N frames.")
    parser.add_argument("--headless", action="store_true", help="Disable OpenCV window rendering.")
    args = parser.parse_args()

    source_mode = SourceMode(args.source)
    if source_mode in {SourceMode.VIDEO, SourceMode.REPLAY} and not args.input:
        parser.error("--input is required for video and replay modes.")

    return VisionOSConfig(
        camera_index=args.camera,
        model_name=args.model,
        confidence_threshold=args.conf,
        image_size=args.imgsz,
        device=args.device,
        max_detections=args.max_detections,
        source_mode=source_mode,
        input_path=args.input,
        record_path=args.record,
        benchmark_output_path=args.benchmark_output,
        overlay_mode=OverlayMode(args.overlay_mode),
        temporal_window_seconds=args.temporal_window,
        max_frames=args.max_frames,
        headless=args.headless,
    )


def _queue_latest(frame_queue: queue.Queue, item) -> bool:
    """Keep only the newest item so slow inference does not build latency."""
    dropped = False
    try:
        frame_queue.put_nowait(item)
    except queue.Full:
        try:
            frame_queue.get_nowait()
            dropped = True
        except queue.Empty:
            pass
        frame_queue.put_nowait(item)
    return dropped


def _build_source(config: VisionOSConfig):
    """Construct the configured frame source."""
    if config.source_mode == SourceMode.WEBCAM:
        return WebcamFrameSource(config.camera_index)
    if config.source_mode == SourceMode.VIDEO:
        return VideoFrameSource(config.input_path or "")
    return ReplayFrameSource(config.input_path or "")


def _process_packet(
    packet: FramePacket,
    detector: YOLODetector | None,
    feature_builder: FeatureBuilder,
    temporal_memory: TemporalMemory,
    context_engine: ContextRulesEngine,
    decision_engine: DecisionEngine,
    explanation_engine: ExplanationEngine,
    benchmark_tracker: BenchmarkTracker,
    recorder: ReplayRecorder | None,
) -> InferenceOutput:
    """Run the full scene pipeline for one packet."""
    start = time.perf_counter()
    detections = packet.replay_detections if packet.replay_detections is not None else detector.detect(packet.frame) if detector else []

    features = feature_builder.build(detections, packet.frame.shape[:2])
    provisional_context = context_engine.infer(features)
    temporal_state = temporal_memory.update(
        packet.timestamp,
        features,
        provisional_context.label,
        provisional_context.confidence,
    )
    scene_context = context_engine.infer(features, temporal_state)
    decision = decision_engine.decide(scene_context, features, temporal_state)
    inference_ms = (time.perf_counter() - start) * 1000.0
    runtime_metrics = benchmark_tracker.record_inference(packet.timestamp, inference_ms, decision.label)
    explanation = explanation_engine.explain(
        decision,
        scene_context,
        features,
        temporal_state,
        runtime_metrics,
    )

    if recorder is not None:
        recorder.write(
            frame_index=packet.frame_index,
            timestamp=packet.timestamp,
            frame_shape=packet.frame.shape[:2],
            detections=detections,
        )

    return InferenceOutput(
        frame_index=packet.frame_index,
        detections=detections,
        decision=decision,
        explanation=explanation,
        runtime_metrics=runtime_metrics,
    )


def _run_streaming_mode(config: VisionOSConfig, source, renderer: FrameRenderer) -> int:
    """Run webcam mode with an asynchronous inference worker for responsive UI."""
    feature_builder = FeatureBuilder()
    temporal_memory = TemporalMemory(config.temporal_window_seconds)
    context_engine = ContextRulesEngine()
    decision_engine = DecisionEngine()
    explanation_engine = ExplanationEngine()
    benchmark_tracker = BenchmarkTracker()
    recorder = (
        ReplayRecorder(config.record_path, config.source_mode)
        if config.record_path and config.source_mode != SourceMode.REPLAY
        else None
    )

    if not source.is_opened():
        print(f"Unable to open {config.source_mode.value} source.", file=sys.stderr)
        return 1

    frame_queue: queue.Queue = queue.Queue(maxsize=1)
    result_queue: queue.Queue = queue.Queue(maxsize=1)
    stop_event = threading.Event()

    def inference_worker() -> None:
        detector = YOLODetector(config)
        while not stop_event.is_set():
            try:
                packet = frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            output = _process_packet(
                packet,
                detector,
                feature_builder,
                temporal_memory,
                context_engine,
                decision_engine,
                explanation_engine,
                benchmark_tracker,
                recorder,
            )
            _queue_latest(result_queue, output)

    worker = threading.Thread(target=inference_worker, name="vision-os-inference", daemon=True)
    worker.start()
    latest_output: InferenceOutput | None = None
    rendered_frames = 0

    try:
        while True:
            packet = source.read()
            if packet is None:
                break
            if _queue_latest(frame_queue, packet):
                benchmark_tracker.note_dropped_frame()

            try:
                while True:
                    latest_output = result_queue.get_nowait()
            except queue.Empty:
                pass

            annotated_frame = packet.frame
            if latest_output is not None:
                annotated_frame = renderer.render(
                    packet.frame,
                    latest_output.detections,
                    latest_output.decision,
                    latest_output.explanation,
                    latest_output.runtime_metrics,
                )

            cv2.imshow("Vision OS", annotated_frame)
            rendered_frames += 1
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            if config.max_frames is not None and rendered_frames >= config.max_frames:
                break
    finally:
        stop_event.set()
        worker.join(timeout=1.0)
        source.close()
        if recorder is not None:
            recorder.close()
        cv2.destroyAllWindows()

    if config.benchmark_output_path:
        benchmark_tracker.write_summary(config.benchmark_output_path)
    summary = benchmark_tracker.summary()
    print(f"Benchmark summary: {summary.to_dict()}")
    return 0


def _run_sequential_mode(config: VisionOSConfig, source, renderer: FrameRenderer) -> int:
    """Run video or replay modes deterministically without dropping frames."""
    feature_builder = FeatureBuilder()
    temporal_memory = TemporalMemory(config.temporal_window_seconds)
    context_engine = ContextRulesEngine()
    decision_engine = DecisionEngine()
    explanation_engine = ExplanationEngine()
    benchmark_tracker = BenchmarkTracker()
    recorder = (
        ReplayRecorder(config.record_path, config.source_mode)
        if config.record_path and config.source_mode != SourceMode.REPLAY
        else None
    )
    detector = None if config.source_mode == SourceMode.REPLAY else YOLODetector(config)

    if not source.is_opened():
        print(f"Unable to open {config.source_mode.value} source.", file=sys.stderr)
        return 1

    processed_frames = 0
    try:
        while True:
            packet = source.read()
            if packet is None:
                break
            output = _process_packet(
                packet,
                detector,
                feature_builder,
                temporal_memory,
                context_engine,
                decision_engine,
                explanation_engine,
                benchmark_tracker,
                recorder,
            )
            processed_frames += 1

            if not config.headless:
                annotated = renderer.render(
                    packet.frame,
                    output.detections,
                    output.decision,
                    output.explanation,
                    output.runtime_metrics,
                )
                cv2.imshow("Vision OS", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if config.max_frames is not None and processed_frames >= config.max_frames:
                break
    finally:
        source.close()
        if recorder is not None:
            recorder.close()
        if not config.headless:
            cv2.destroyAllWindows()

    if config.benchmark_output_path:
        benchmark_tracker.write_summary(config.benchmark_output_path)
    summary = benchmark_tracker.summary()
    print(f"Benchmark summary: {summary.to_dict()}")
    return 0


def main() -> int:
    """Run the end-to-end source loop until the user quits or the source is exhausted."""
    config = parse_args()
    renderer = FrameRenderer(config.overlay_mode)
    source = _build_source(config)

    if config.source_mode == SourceMode.WEBCAM and not config.headless:
        return _run_streaming_mode(config, source, renderer)
    return _run_sequential_mode(config, source, renderer)


if __name__ == "__main__":
    raise SystemExit(main())
