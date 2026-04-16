"""Frame sources plus replay recording and playback helpers."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from common.models import Detection, ReplayRecord, SourceMode


@dataclass(slots=True)
class FramePacket:
    """One runtime input frame, optionally carrying replay detections."""

    frame_index: int
    timestamp: float
    frame: np.ndarray
    source_mode: SourceMode
    replay_detections: list[Detection] | None = None


class WebcamFrameSource:
    """Read live frames from an attached webcam."""

    def __init__(self, camera_index: int) -> None:
        self._capture = cv2.VideoCapture(camera_index)
        self._frame_index = 0

    def read(self) -> FramePacket | None:
        ok, frame = self._capture.read()
        if not ok:
            return None
        packet = FramePacket(
            frame_index=self._frame_index,
            timestamp=time.perf_counter(),
            frame=frame,
            source_mode=SourceMode.WEBCAM,
        )
        self._frame_index += 1
        return packet

    def is_opened(self) -> bool:
        return self._capture.isOpened()

    def close(self) -> None:
        self._capture.release()


class VideoFrameSource:
    """Read frames from a local video file for deterministic demos."""

    def __init__(self, input_path: str) -> None:
        self._capture = cv2.VideoCapture(input_path)
        self._frame_index = 0

    def read(self) -> FramePacket | None:
        ok, frame = self._capture.read()
        if not ok:
            return None
        millis = self._capture.get(cv2.CAP_PROP_POS_MSEC)
        packet = FramePacket(
            frame_index=self._frame_index,
            timestamp=millis / 1000.0 if millis > 0 else float(self._frame_index),
            frame=frame,
            source_mode=SourceMode.VIDEO,
        )
        self._frame_index += 1
        return packet

    def is_opened(self) -> bool:
        return self._capture.isOpened()

    def close(self) -> None:
        self._capture.release()


class ReplayFrameSource:
    """Replay a saved detection session without requiring a camera."""

    def __init__(self, input_path: str) -> None:
        self._path = Path(input_path)
        self._file = self._path.open("r", encoding="utf-8")

    def read(self) -> FramePacket | None:
        line = self._file.readline()
        if not line:
            return None
        record = ReplayRecord.from_dict(json.loads(line))
        frame = np.zeros((record.frame_shape[0], record.frame_shape[1], 3), dtype=np.uint8)
        return FramePacket(
            frame_index=record.frame_index,
            timestamp=record.timestamp,
            frame=frame,
            source_mode=SourceMode.REPLAY,
            replay_detections=record.detections,
        )

    def is_opened(self) -> bool:
        return True

    def close(self) -> None:
        self._file.close()


class ReplayRecorder:
    """Write replayable session artifacts as line-delimited JSON."""

    def __init__(self, output_path: str, source_mode: SourceMode) -> None:
        self._source_mode = source_mode
        self._file = Path(output_path).open("w", encoding="utf-8")

    def write(
        self,
        frame_index: int,
        timestamp: float,
        frame_shape: tuple[int, int],
        detections: list[Detection],
    ) -> None:
        record = ReplayRecord(
            frame_index=frame_index,
            timestamp=timestamp,
            frame_shape=frame_shape,
            detections=detections,
            source_mode=self._source_mode,
        )
        self._file.write(json.dumps(record.to_dict()) + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()
