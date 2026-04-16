"""Draw detections, labels, and reasoning on top of video frames."""

from __future__ import annotations

import textwrap

import cv2
import numpy as np

from common.models import Decision, Detection, Explanation


class FrameRenderer:
    """Overlay object boxes and scene-level insights on the current frame."""

    BOX_COLOR = (80, 220, 120)
    HEADER_COLOR = (20, 20, 20)
    HEADER_TEXT = (245, 245, 245)

    def render(
        self,
        frame: np.ndarray,
        detections: list[Detection],
        decision: Decision,
        explanation: Explanation,
    ) -> np.ndarray:
        """Create an annotated frame without mutating the caller's input."""
        annotated = frame.copy()

        for detection in detections:
            bbox = detection.bbox
            cv2.rectangle(
                annotated,
                (bbox.x1, bbox.y1),
                (bbox.x2, bbox.y2),
                self.BOX_COLOR,
                2,
            )
            label = f"{detection.label} {detection.confidence:.2f}"
            cv2.putText(
                annotated,
                label,
                (bbox.x1, max(20, bbox.y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                self.BOX_COLOR,
                2,
                cv2.LINE_AA,
            )

        self._draw_header(annotated, decision, explanation)
        return annotated

    def _draw_header(self, frame: np.ndarray, decision: Decision, explanation: Explanation) -> None:
        """Draw a top banner with the scene label, action, and wrapped explanation."""
        panel_height = 110
        cv2.rectangle(frame, (0, 0), (frame.shape[1], panel_height), self.HEADER_COLOR, -1)

        title = f"{decision.label.value} ({decision.confidence:.2f})"
        action = decision.action
        cv2.putText(
            frame,
            title,
            (16, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            self.HEADER_TEXT,
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            frame,
            action,
            (16, 58),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            self.HEADER_TEXT,
            2,
            cv2.LINE_AA,
        )

        for index, line in enumerate(textwrap.wrap(explanation.summary, width=76)[:2]):
            cv2.putText(
                frame,
                line,
                (16, 84 + index * 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.54,
                self.HEADER_TEXT,
                1,
                cv2.LINE_AA,
            )
