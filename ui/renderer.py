"""Draw detections, labels, and reasoning on top of video frames."""

from __future__ import annotations

from dataclasses import dataclass
import textwrap

import cv2
import numpy as np

from common.profile import OverlaySection, ProfilePresentation
from common.models import BoundingBox, Decision, Detection, Explanation, OverlayMode, RuntimeMetrics
from zones.models import ZoneRuntimeState


@dataclass(slots=True, frozen=True)
class _TextStyle:
    """Shared drawing settings for one text block in the overlay."""

    scale: float
    thickness: int
    color: tuple[int, int, int]


@dataclass(slots=True, frozen=True)
class _LayoutRow:
    """One measured line of text with its final vertical placement."""

    text: str
    x: int
    baseline_y: int
    top: int
    bottom: int
    style: _TextStyle


@dataclass(slots=True, frozen=True)
class _HeaderLayout:
    """Measured header panel and the rows it will contain."""

    panel_height: int
    rows: list[_LayoutRow]


class FrameRenderer:
    """Overlay object boxes and scene-level insights on the current frame."""

    BOX_COLOR = (80, 220, 120)
    HEADER_COLOR = (20, 20, 20)
    HEADER_TEXT = (245, 245, 245)
    RISK_COLOR = (70, 180, 255)
    ZONE_COLOR = (255, 200, 90)
    FONT = cv2.FONT_HERSHEY_SIMPLEX
    PANEL_PADDING_X = 16
    PANEL_PADDING_Y = 16
    LINE_GAP = 8
    SECTION_GAP = 6
    LABEL_MARGIN = 8

    TITLE_STYLE = _TextStyle(scale=0.9, thickness=2, color=HEADER_TEXT)
    ACTION_STYLE = _TextStyle(scale=0.62, thickness=2, color=HEADER_TEXT)
    BODY_STYLE = _TextStyle(scale=0.52, thickness=1, color=HEADER_TEXT)
    METRIC_STYLE = _TextStyle(scale=0.48, thickness=1, color=HEADER_TEXT)
    DEBUG_STYLE = _TextStyle(scale=0.46, thickness=1, color=HEADER_TEXT)
    EMPHASIS_STYLE = _TextStyle(scale=0.46, thickness=1, color=RISK_COLOR)
    RUNTIME_STYLE = _TextStyle(scale=0.46, thickness=1, color=HEADER_TEXT)
    DETECTION_LABEL_STYLE = _TextStyle(scale=0.55, thickness=2, color=BOX_COLOR)

    def __init__(
        self,
        overlay_mode: OverlayMode = OverlayMode.COMPACT,
        presentation: ProfilePresentation | None = None,
    ) -> None:
        self.overlay_mode = overlay_mode
        self.presentation = presentation or ProfilePresentation(overlay_mode=overlay_mode)

    def render(
        self,
        frame: np.ndarray,
        detections: list[Detection],
        decision: Decision,
        explanation: Explanation,
        runtime_metrics: RuntimeMetrics,
        zone_states: tuple[ZoneRuntimeState, ...] = (),
    ) -> np.ndarray:
        """Create an annotated frame without mutating the caller's input."""
        annotated = frame.copy()
        header_bottom = self._draw_header(annotated, decision, explanation, runtime_metrics)
        self._draw_zone_overlays(annotated, zone_states, header_bottom)

        for detection in detections:
            bbox = detection.bbox
            cv2.rectangle(
                annotated,
                (bbox.x1, bbox.y1),
                (bbox.x2, bbox.y2),
                self.BOX_COLOR,
                2,
            )
            label_prefix = f"{detection.label}#{detection.track_id}" if detection.track_id is not None else detection.label
            label = f"{label_prefix} {detection.confidence:.2f}"
            label_baseline = self._compute_detection_label_baseline(
                bbox=bbox,
                label_text=label,
                header_bottom=header_bottom,
            )
            cv2.putText(
                annotated,
                label,
                (bbox.x1, label_baseline),
                self.FONT,
                self.DETECTION_LABEL_STYLE.scale,
                self.DETECTION_LABEL_STYLE.color,
                self.DETECTION_LABEL_STYLE.thickness,
                cv2.LINE_AA,
            )

        return annotated

    def _draw_header(
        self,
        frame: np.ndarray,
        decision: Decision,
        explanation: Explanation,
        runtime_metrics: RuntimeMetrics,
    ) -> int:
        """Draw a measured top banner and return its bottom Y coordinate."""
        layout = self._build_header_layout(
            frame_width=frame.shape[1],
            frame_height=frame.shape[0],
            decision=decision,
            explanation=explanation,
            runtime_metrics=runtime_metrics,
        )
        cv2.rectangle(frame, (0, 0), (frame.shape[1], layout.panel_height), self.HEADER_COLOR, -1)
        for row in layout.rows:
            cv2.putText(
                frame,
                row.text,
                (row.x, row.baseline_y),
                self.FONT,
                row.style.scale,
                row.style.color,
                row.style.thickness,
                cv2.LINE_AA,
            )
        return layout.panel_height

    def _build_header_layout(
        self,
        frame_width: int,
        frame_height: int,
        decision: Decision,
        explanation: Explanation,
        runtime_metrics: RuntimeMetrics,
    ) -> _HeaderLayout:
        """Measure header rows before drawing so wrapped text never collides."""
        rows: list[_LayoutRow] = []
        cursor_top = self.PANEL_PADDING_Y
        content_width = max(220, frame_width - (self.PANEL_PADDING_X * 2))

        title = f"{decision.label.value} ({decision.confidence:.2f})"
        cursor_top = self._append_lines(rows, [title], self.TITLE_STYLE, cursor_top)
        cursor_top = self._append_lines(rows, [explanation.action], self.ACTION_STYLE, cursor_top)

        summary_lines = self._wrap_text_to_width(
            explanation.compact_summary,
            max_width=content_width,
            style=self.BODY_STYLE,
            max_lines=2,
        )
        cursor_top = self._append_lines(rows, summary_lines, self.BODY_STYLE, cursor_top)

        sections = self._active_sections()
        if OverlaySection.SCORES in sections:
            metric_lines = self._wrap_text_to_width(
                self._format_score_line(explanation.scores),
                max_width=content_width,
                style=self.METRIC_STYLE,
                max_lines=2,
            )
            cursor_top = self._append_lines(rows, metric_lines, self.METRIC_STYLE, cursor_top)

        if OverlaySection.EVENTS in sections and explanation.recent_events:
            event_lines = self._wrap_text_to_width(
                f"Events: {', '.join(explanation.recent_events)}",
                max_width=content_width,
                style=self.BODY_STYLE if self.overlay_mode == OverlayMode.COMPACT else self.EMPHASIS_STYLE,
                max_lines=2,
            )
            cursor_top = self._append_lines(
                rows,
                event_lines,
                self.BODY_STYLE if self.overlay_mode == OverlayMode.COMPACT else self.EMPHASIS_STYLE,
                cursor_top,
            )

        if OverlaySection.TRIGGERS in sections and explanation.recent_triggers:
            trigger_lines = self._wrap_text_to_width(
                f"Triggers: {', '.join(explanation.recent_triggers)}",
                max_width=content_width,
                style=self.BODY_STYLE if self.overlay_mode == OverlayMode.COMPACT else self.EMPHASIS_STYLE,
                max_lines=2,
            )
            cursor_top = self._append_lines(
                rows,
                trigger_lines,
                self.BODY_STYLE if self.overlay_mode == OverlayMode.COMPACT else self.EMPHASIS_STYLE,
                cursor_top,
            )

        if OverlaySection.ZONES in sections and explanation.zone_summaries:
            zone_lines = self._wrap_text_to_width(
                f"Zones: {', '.join(explanation.zone_summaries)}",
                max_width=content_width,
                style=self.BODY_STYLE,
                max_lines=3 if self.overlay_mode == OverlayMode.DEBUG else 2,
            )
            cursor_top = self._append_lines(rows, zone_lines, self.BODY_STYLE, cursor_top)

        if self.overlay_mode == OverlayMode.DEBUG:
            for line in explanation.debug_lines[:4]:
                debug_lines = self._wrap_text_to_width(
                    line,
                    max_width=content_width,
                    style=self.DEBUG_STYLE,
                )
                cursor_top = self._append_lines(rows, debug_lines, self.DEBUG_STYLE, cursor_top)
            if explanation.risk_flags:
                risk_lines = self._wrap_text_to_width(
                    f"Risks: {', '.join(explanation.risk_flags)}",
                    max_width=content_width,
                    style=self.EMPHASIS_STYLE,
                    max_lines=2,
                )
                cursor_top = self._append_lines(rows, risk_lines, self.EMPHASIS_STYLE, cursor_top)
            if OverlaySection.SPATIAL in sections:
                spatial_line = self._find_debug_line(explanation, prefix="Spatial:")
                if spatial_line is not None:
                    spatial_lines = self._wrap_text_to_width(
                        spatial_line,
                        max_width=content_width,
                        style=self.DEBUG_STYLE,
                        max_lines=2,
                    )
                    cursor_top = self._append_lines(rows, spatial_lines, self.DEBUG_STYLE, cursor_top)

        if OverlaySection.RUNTIME in sections:
            runtime_lines = self._wrap_text_to_width(
                self._format_runtime_line(runtime_metrics),
                max_width=content_width,
                style=self.RUNTIME_STYLE,
                max_lines=2,
            )
            self._append_lines(rows, runtime_lines, self.RUNTIME_STYLE, cursor_top, add_section_gap=False)

        content_bottom = rows[-1].bottom if rows else self.PANEL_PADDING_Y
        panel_height = min(
            frame_height,
            max(self._minimum_panel_height(), content_bottom + self.PANEL_PADDING_Y),
        )
        return _HeaderLayout(panel_height=panel_height, rows=rows)

    def _append_lines(
        self,
        rows: list[_LayoutRow],
        lines: list[str],
        style: _TextStyle,
        cursor_top: int,
        *,
        add_section_gap: bool = True,
    ) -> int:
        """Add a wrapped text block to the layout and return the next top offset."""
        for line in lines:
            _, text_height, baseline = self._measure_text(line, style)
            row = _LayoutRow(
                text=line,
                x=self.PANEL_PADDING_X,
                baseline_y=cursor_top + text_height,
                top=cursor_top,
                bottom=cursor_top + text_height + baseline,
                style=style,
            )
            rows.append(row)
            cursor_top = row.bottom + self.LINE_GAP
        if lines and add_section_gap:
            cursor_top += self.SECTION_GAP
        return cursor_top

    def _wrap_text_to_width(
        self,
        text: str,
        *,
        max_width: int,
        style: _TextStyle,
        max_lines: int | None = None,
    ) -> list[str]:
        """Wrap text by rendered pixel width instead of character count."""
        if not text:
            return []

        wrapped_lines: list[str] = []
        source_lines = textwrap.wrap(text, width=max(12, int(max_width / 10)), break_long_words=False) or [text]
        for source_line in source_lines:
            words = source_line.split()
            if not words:
                wrapped_lines.append("")
                continue

            current_line = words[0]
            for word in words[1:]:
                candidate = f"{current_line} {word}"
                candidate_width, _, _ = self._measure_text(candidate, style)
                if candidate_width <= max_width:
                    current_line = candidate
                    continue

                wrapped_lines.append(current_line)
                current_line = word

            wrapped_lines.append(current_line)
            if max_lines is not None and len(wrapped_lines) >= max_lines:
                return wrapped_lines[:max_lines]

        return wrapped_lines[:max_lines] if max_lines is not None else wrapped_lines

    def _measure_text(self, text: str, style: _TextStyle) -> tuple[int, int, int]:
        """Return rendered width, height, and baseline for a text fragment."""
        (width, height), baseline = cv2.getTextSize(text or " ", self.FONT, style.scale, style.thickness)
        return width, height, baseline

    def _format_score_line(self, scores: dict[str, float]) -> str:
        """Format the main score row with concise labels."""
        return (
            f"Scores: focus {scores['focus']:.2f} | distract {scores['distraction']:.2f} | "
            f"collab {scores['collaboration']:.2f} | stability {scores['stability']:.2f}"
        )

    def _format_runtime_line(self, runtime_metrics: RuntimeMetrics) -> str:
        """Format the runtime summary row."""
        return (
            f"Runtime: frames {runtime_metrics.frames_processed} | fps {runtime_metrics.fps:.2f} | "
            f"avg {runtime_metrics.average_inference_ms:.1f}ms | dropped {runtime_metrics.dropped_frames}"
        )

    def _minimum_panel_height(self) -> int:
        """Keep a modest baseline header size even for short summaries."""
        return 136 if self.overlay_mode == OverlayMode.COMPACT else 220

    def _active_sections(self) -> tuple[OverlaySection, ...]:
        """Return the section set for the current overlay density."""
        if self.overlay_mode == OverlayMode.DEBUG:
            return self.presentation.debug_sections
        return self.presentation.compact_sections

    def _find_debug_line(self, explanation: Explanation, *, prefix: str) -> str | None:
        """Look up one generated debug line by its stable prefix."""
        for line in explanation.debug_lines:
            if line.startswith(prefix):
                return line
        return None

    def _compute_detection_label_baseline(
        self,
        *,
        bbox: BoundingBox,
        label_text: str,
        header_bottom: int,
    ) -> int:
        """Keep detection labels clear of the header when boxes start near the top."""
        _, text_height, baseline = self._measure_text(label_text, self.DETECTION_LABEL_STYLE)
        preferred_baseline = bbox.y1 - self.LABEL_MARGIN
        safe_baseline = header_bottom + text_height + baseline + self.LABEL_MARGIN
        if preferred_baseline >= safe_baseline:
            return preferred_baseline
        return max(bbox.y1 + text_height + self.LABEL_MARGIN, safe_baseline)

    def _draw_zone_overlays(
        self,
        frame: np.ndarray,
        zone_states: tuple[ZoneRuntimeState, ...],
        header_bottom: int,
    ) -> None:
        """Draw configured zone polygons and their current label."""
        for zone_state in zone_states:
            if not zone_state.polygon:
                continue

            polygon = np.array([(int(point.x), int(point.y)) for point in zone_state.polygon], dtype=np.int32)
            cv2.polylines(frame, [polygon], isClosed=True, color=self.ZONE_COLOR, thickness=2)

            min_x = int(min(point.x for point in zone_state.polygon))
            min_y = int(min(point.y for point in zone_state.polygon))
            label = f"{zone_state.zone_name}: {zone_state.context.label.value}"
            _, text_height, baseline = self._measure_text(label, self.DEBUG_STYLE)
            baseline_y = max(
                header_bottom + text_height + baseline + self.LABEL_MARGIN,
                min_y + text_height + baseline + self.LABEL_MARGIN,
            )
            cv2.putText(
                frame,
                label,
                (min_x + 4, baseline_y),
                self.FONT,
                self.DEBUG_STYLE.scale,
                self.ZONE_COLOR,
                self.DEBUG_STYLE.thickness,
                cv2.LINE_AA,
            )
