"""Health reporting for background inference workers."""

from __future__ import annotations

import queue


class WorkerFailure(RuntimeError):
    """Raised when the background inference worker reports an exception."""


class HealthMonitor:
    """Small exception queue that lets the UI loop fail loudly with context."""

    def __init__(self) -> None:
        self._exceptions: queue.Queue[tuple[str, Exception]] = queue.Queue()

    def report_exception(self, stage: str, exc: Exception) -> None:
        self._exceptions.put((stage, exc))

    def raise_if_unhealthy(self) -> None:
        try:
            stage, exc = self._exceptions.get_nowait()
        except queue.Empty:
            return
        raise WorkerFailure(f"Worker failed during {stage}: {exc}") from exc
