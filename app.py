"""Entry point for the Vision OS real-time webcam pipeline."""

from __future__ import annotations

import argparse
import queue
import sys
import threading
from dataclasses import dataclass

import cv2

from common.config import VisionOSConfig
from common.models import Decision, Detection, Explanation
from context.rules import ContextRulesEngine
from decision.engine import DecisionEngine
from explain.explain import ExplanationEngine
from features.builder import FeatureBuilder
from perception.detector import YOLODetector
from ui.renderer import FrameRenderer


@dataclass(slots=True)
class InferenceOutput:
    """Bundle the latest inference result for the rendering loop."""

    detections: list[Detection]
    decision: Decision
    explanation: Explanation


def parse_args() -> VisionOSConfig:
    """Parse CLI arguments into a runtime config object."""
    parser = argparse.ArgumentParser(description="Run Vision OS on a webcam feed.")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index.")
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
    args = parser.parse_args()
    return VisionOSConfig(
        camera_index=args.camera,
        model_name=args.model,
        confidence_threshold=args.conf,
        image_size=args.imgsz,
        device=args.device,
        max_detections=args.max_detections,
    )


def _queue_latest(frame_queue: queue.Queue, frame) -> None:
    """Keep only the newest frame so slow inference does not build latency."""
    try:
        frame_queue.put_nowait(frame)
    except queue.Full:
        try:
            frame_queue.get_nowait()
        except queue.Empty:
            pass
        frame_queue.put_nowait(frame)


def main() -> int:
    """Run the end-to-end webcam loop until the user quits."""
    config = parse_args()
    feature_builder = FeatureBuilder()
    context_engine = ContextRulesEngine()
    decision_engine = DecisionEngine()
    renderer = FrameRenderer()

    capture = cv2.VideoCapture(config.camera_index)
    if not capture.isOpened():
        print(f"Unable to open webcam at index {config.camera_index}.", file=sys.stderr)
        return 1

    frame_queue: queue.Queue = queue.Queue(maxsize=1)
    result_queue: queue.Queue = queue.Queue(maxsize=1)
    stop_event = threading.Event()

    def inference_worker() -> None:
        """Run heavy YOLO inference off the UI loop and publish only the latest result."""
        detector = YOLODetector(config)
        explanation_engine = ExplanationEngine()

        while not stop_event.is_set():
            try:
                frame = frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            detections = detector.detect(frame)
            features = feature_builder.build(detections, frame.shape[:2])
            scene_context = context_engine.infer(features)
            decision = decision_engine.decide(scene_context, features)
            explanation = explanation_engine.explain(decision, scene_context, features)
            output = InferenceOutput(
                detections=detections,
                decision=decision,
                explanation=explanation,
            )
            _queue_latest(result_queue, output)

    worker = threading.Thread(target=inference_worker, name="vision-os-inference", daemon=True)
    worker.start()
    latest_output: InferenceOutput | None = None

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                print("Failed to read a frame from the webcam.", file=sys.stderr)
                return 1

            _queue_latest(frame_queue, frame.copy())
            try:
                while True:
                    latest_output = result_queue.get_nowait()
            except queue.Empty:
                pass

            if latest_output is None:
                annotated_frame = frame
            else:
                annotated_frame = renderer.render(
                    frame,
                    latest_output.detections,
                    latest_output.decision,
                    latest_output.explanation,
                )

            cv2.imshow("Vision OS", annotated_frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        stop_event.set()
        worker.join(timeout=1.0)
        capture.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
