"""Run YOLO object detection and return structured detections."""

from __future__ import annotations

from typing import Any

import numpy as np

from common.config import VisionOSConfig
from common.models import BoundingBox, Detection


class YOLODetector:
    """Thin wrapper around Ultralytics YOLO for predictable app integration."""

    def __init__(self, config: VisionOSConfig) -> None:
        self.config = config
        try:
            from ultralytics import YOLO
        except ImportError as exc:  # pragma: no cover - exercised in runtime, not tests
            raise RuntimeError(
                "Ultralytics is not installed. Run `python -m pip install -e \".[dev]\"`."
            ) from exc

        self.model = YOLO(config.model_name)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Infer objects in a frame and normalize them into dataclasses."""
        predict_kwargs: dict[str, Any] = {
            "source": frame,
            "conf": self.config.confidence_threshold,
            "imgsz": self.config.image_size,
            "verbose": False,
            "max_det": self.config.max_detections,
        }
        if self.config.device is not None:
            predict_kwargs["device"] = self.config.device

        results = self.model.predict(**predict_kwargs)
        if not results:
            return []

        frame_height, frame_width = frame.shape[:2]
        boxes = results[0].boxes
        names = results[0].names
        detections: list[Detection] = []

        for box in boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            width = max(0, x2 - x1)
            height = max(0, y2 - y1)
            area_ratio = (width * height) / max(1, frame_width * frame_height)
            class_id = int(box.cls[0].item())
            detections.append(
                Detection(
                    label=str(names[class_id]),
                    confidence=float(box.conf[0].item()),
                    bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                    area_ratio=area_ratio,
                    class_id=class_id,
                )
            )

        return detections

