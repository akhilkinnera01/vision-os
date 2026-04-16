"""Draw detections, labels, and reasoning on top of video frames."""

from __future__ import annotations

import textwrap

import cv2
import numpy as np

from common.models import Decision, Detection, Explanation, OverlayMode, RuntimeMetrics


class FrameRenderer:
    """Overlay object boxes and scene-level insights on the current frame."""

    BOX_COLOR = (80, 220, 120)
    HEADER_COLOR = (20, 20, 20)
    HEADER_TEXT = (245, 245, 245)
    RISK_COLOR = (70, 180, 255)

    def __init__(self, overlay_mode: OverlayMode = OverlayMode.COMPACT) -> None:
        self.overlay_mode = overlay_mode

    def render(
        self,
        frame: np.ndarray,
        detections: list[Detection],
        decision: Decision,
        explanation: Explanation,
        runtime_metrics: RuntimeMetrics,
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

        self._draw_header(annotated, decision, explanation, runtime_metrics)
        return annotated

    def _draw_header(
        self,
        frame: np.ndarray,
        decision: Decision,
        explanation: Explanation,
        runtime_metrics: RuntimeMetrics,
    ) -> None:
        """Draw a top banner with the scene label, action, and wrapped explanation."""
        panel_height = 130 if self.overlay_mode == OverlayMode.COMPACT else 235
        cv2.rectangle(frame, (0, 0), (frame.shape[1], panel_height), self.HEADER_COLOR, -1)

        title = f"{decision.label.value} ({decision.confidence:.2f})"
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
            explanation.action,
            (16, 58),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.62,
            self.HEADER_TEXT,
            2,
            cv2.LINE_AA,
        )

        summary_lines = textwrap.wrap(explanation.compact_summary, width=86)[:2]
        for index, line in enumerate(summary_lines):
            cv2.putText(
                frame,
                line,
                (16, 84 + index * 18),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.52,
                self.HEADER_TEXT,
                1,
                cv2.LINE_AA,
            )

        metrics_line = (
            f"focus {explanation.scores['focus']:.2f}  "
            f"distraction {explanation.scores['distraction']:.2f}  "
            f"collaboration {explanation.scores['collaboration']:.2f}  "
            f"stability {explanation.scores['stability']:.2f}"
        )
        cv2.putText(
            frame,
            metrics_line,
            (16, 118),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.48,
            self.HEADER_TEXT,
            1,
            cv2.LINE_AA,
        )

        if self.overlay_mode == OverlayMode.DEBUG:
            current_y = 145
            for line in explanation.debug_lines[:4]:
                for wrapped in textwrap.wrap(line, width=92):
                    cv2.putText(
                        frame,
                        wrapped,
                        (16, current_y),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.46,
                        self.HEADER_TEXT,
                        1,
                        cv2.LINE_AA,
                    )
                    current_y += 18
            if explanation.risk_flags:
                cv2.putText(
                    frame,
                    f"Risks: {', '.join(explanation.risk_flags)}",
                    (16, min(panel_height - 12, current_y + 6)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.46,
                    self.RISK_COLOR,
                    1,
                    cv2.LINE_AA,
                )

        runtime_line = (
            f"frames {runtime_metrics.frames_processed}  "
            f"fps {runtime_metrics.fps:.2f}  "
            f"avg {runtime_metrics.average_inference_ms:.1f}ms  "
            f"dropped {runtime_metrics.dropped_frames}"
        )
        cv2.putText(
            frame,
            runtime_line,
            (16, panel_height - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.46,
            self.HEADER_TEXT,
            1,
            cv2.LINE_AA,
        )
