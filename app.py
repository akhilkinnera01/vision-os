"""Entry point for the Vision OS webcam, video, and replay runtime."""

from __future__ import annotations

import argparse
import queue
import sys
import threading
from pathlib import Path

import cv2

from common.config import VisionOSConfig
from common.models import OverlayMode, SourceMode
from common.policy import PolicyValidationError, load_policy
from runtime.benchmark import BenchmarkTracker
from runtime.pipeline import InferenceOutput, VisionPipeline
from runtime.io import ReplayFrameSource, ReplayRecorder, VideoFrameSource, WebcamFrameSource
from telemetry.health import HealthMonitor
from telemetry.logging import VisionLogger
from ui.renderer import FrameRenderer
from zones import ZoneConfigError, load_zones


def parse_args() -> VisionOSConfig:
    """Parse CLI arguments into a runtime config object."""
    parser = argparse.ArgumentParser(description="Run Vision OS on a webcam, video, or replay feed.")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index.")
    parser.add_argument("--source", choices=[mode.value for mode in SourceMode], default="webcam")
    parser.add_argument("--input", help="Path to a video file or replay artifact.")
    parser.add_argument("--zones-file", help="Optional path to a YAML file that defines static polygon zones.")
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
    parser.add_argument("--policy", default="default", help="Named policy to load from the policies/ directory.")
    parser.add_argument("--policy-file", help="Optional path to a custom policy YAML file.")
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
    parser.add_argument("--log-json", action="store_true", help="Emit structured JSON logs to stderr.")
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
        zones_path=args.zones_file,
        record_path=args.record,
        benchmark_output_path=args.benchmark_output,
        policy_name=args.policy,
        policy_path=args.policy_file,
        overlay_mode=OverlayMode(args.overlay_mode),
        temporal_window_seconds=args.temporal_window,
        max_frames=args.max_frames,
        headless=args.headless,
        log_json=args.log_json,
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


def _validate_input_path(config: VisionOSConfig) -> None:
    """Fail fast with a readable CLI error when file-backed inputs are missing."""
    if config.source_mode in {SourceMode.VIDEO, SourceMode.REPLAY}:
        input_path = Path(config.input_path or "")
        if not input_path.is_file():
            source_name = "video" if config.source_mode == SourceMode.VIDEO else "replay"
            raise FileNotFoundError(f"{source_name.capitalize()} input not found: {input_path}")

    if config.zones_path:
        zones_path = Path(config.zones_path)
        if not zones_path.is_file():
            raise FileNotFoundError(f"Zone config not found: {zones_path}")


def _log_run_started(config: VisionOSConfig, policy_name: str, zone_count: int, logger: VisionLogger) -> None:
    """Emit one structured record that captures the active runtime configuration."""
    logger.log(
        "run_started",
        mode=config.source_mode.value,
        policy=policy_name,
        zone_count=zone_count,
        overlay_mode=config.overlay_mode.value,
        headless=config.headless,
        temporal_window_seconds=config.temporal_window_seconds,
        zones_path=config.zones_path,
        record_path=config.record_path,
        benchmark_output_path=config.benchmark_output_path,
    )


def _finalize_run(
    config: VisionOSConfig,
    benchmark_tracker: BenchmarkTracker,
    logger: VisionLogger,
) -> int:
    """Persist run artifacts, emit completion logs, and print the benchmark summary."""
    if config.record_path and config.source_mode != SourceMode.REPLAY:
        logger.log("artifact_written", kind="replay", path=config.record_path, mode=config.source_mode.value)

    if config.benchmark_output_path:
        benchmark_tracker.write_summary(config.benchmark_output_path)
        logger.log("artifact_written", kind="benchmark", path=config.benchmark_output_path, mode=config.source_mode.value)

    summary = benchmark_tracker.summary()
    logger.log(
        "run_completed",
        mode=config.source_mode.value,
        frames=summary.frames_processed,
        fps=summary.fps,
        average_inference_ms=summary.average_inference_ms,
        dropped_frames=summary.dropped_frames,
        decision_switch_rate=summary.decision_switch_rate,
        scene_stability_score=summary.scene_stability_score,
    )
    print(f"Benchmark summary: {summary.to_dict()}")
    return 0


def _should_use_streaming_runtime(config: VisionOSConfig) -> bool:
    """Webcam mode stays on the real-time worker path even when rendering is disabled."""
    return config.source_mode == SourceMode.WEBCAM


def _run_streaming_mode(config: VisionOSConfig, policy, zones, source, renderer: FrameRenderer, logger: VisionLogger) -> int:
    """Run webcam mode with an asynchronous inference worker for responsive UI."""
    if not source.is_opened():
        logger.log("source_open_failed", mode=config.source_mode.value, input_path=config.input_path, camera=config.camera_index)
        print(f"Unable to open {config.source_mode.value} source.", file=sys.stderr)
        source.close()
        return 1

    benchmark_tracker = BenchmarkTracker()
    health_monitor = HealthMonitor()
    recorder = (
        ReplayRecorder(config.record_path, config.source_mode)
        if config.record_path and config.source_mode != SourceMode.REPLAY
        else None
    )

    frame_queue: queue.Queue = queue.Queue(maxsize=1)
    result_queue: queue.Queue = queue.Queue(maxsize=1)
    stop_event = threading.Event()

    def inference_worker() -> None:
        pipeline = VisionPipeline(config, policy=policy, zones=tuple(zones), benchmark_tracker=benchmark_tracker)
        while not stop_event.is_set():
            try:
                packet = frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                output = pipeline.process(packet)
                if recorder is not None:
                    recorder.write(
                        frame_index=packet.frame_index,
                        timestamp=packet.timestamp,
                        frame_shape=packet.frame.shape[:2],
                        detections=output.detections,
                        events=output.events,
                    )
                _queue_latest(result_queue, output)
            except Exception as exc:  # pragma: no cover - exercised in runtime
                health_monitor.report_exception("pipeline", exc)
                stop_event.set()
                return

    worker = threading.Thread(target=inference_worker, name="vision-os-inference", daemon=True)
    worker.start()
    latest_output: InferenceOutput | None = None
    processed_frames = 0

    try:
        while True:
            health_monitor.raise_if_unhealthy()
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

            if not config.headless:
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
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            processed_frames += 1
            if config.max_frames is not None and processed_frames >= config.max_frames:
                break
    finally:
        stop_event.set()
        worker.join(timeout=1.0)
        health_monitor.raise_if_unhealthy()
        source.close()
        if recorder is not None:
            recorder.close()
        if not config.headless:
            cv2.destroyAllWindows()

    return _finalize_run(config, benchmark_tracker, logger)


def _run_sequential_mode(config: VisionOSConfig, policy, zones, source, renderer: FrameRenderer, logger: VisionLogger) -> int:
    """Run video or replay modes deterministically without dropping frames."""
    if not source.is_opened():
        logger.log("source_open_failed", mode=config.source_mode.value, input_path=config.input_path)
        print(f"Unable to open {config.source_mode.value} source.", file=sys.stderr)
        source.close()
        return 1

    benchmark_tracker = BenchmarkTracker()
    recorder = (
        ReplayRecorder(config.record_path, config.source_mode)
        if config.record_path and config.source_mode != SourceMode.REPLAY
        else None
    )
    pipeline = VisionPipeline(config, policy=policy, zones=tuple(zones), benchmark_tracker=benchmark_tracker)

    processed_frames = 0
    try:
        while True:
            packet = source.read()
            if packet is None:
                break
            output = pipeline.process(packet)
            if recorder is not None:
                recorder.write(
                    frame_index=packet.frame_index,
                    timestamp=packet.timestamp,
                    frame_shape=packet.frame.shape[:2],
                    detections=output.detections,
                    events=output.events,
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

    return _finalize_run(config, benchmark_tracker, logger)


def main() -> int:
    """Run the end-to-end source loop until the user quits or the source is exhausted."""
    try:
        config = parse_args()
        _validate_input_path(config)
        policy = load_policy(name=config.policy_name, path=config.policy_path)
        zones = load_zones(config.zones_path) if config.zones_path else ()
        logger = VisionLogger(config.log_json)
        renderer = FrameRenderer(config.overlay_mode)
        source = _build_source(config)
    except (FileNotFoundError, PolicyValidationError, ZoneConfigError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    _log_run_started(config, policy.name, len(zones), logger)
    if _should_use_streaming_runtime(config):
        return _run_streaming_mode(config, policy, zones, source, renderer, logger)
    return _run_sequential_mode(config, policy, zones, source, renderer, logger)


if __name__ == "__main__":
    raise SystemExit(main())
