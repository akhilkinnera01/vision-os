"""Stage timing utilities for per-frame runtime measurement."""

from __future__ import annotations

import time
from contextlib import contextmanager


class StageTimer:
    """Collect lightweight stage timings for a single pipeline pass."""

    def __init__(self) -> None:
        self._timings: dict[str, float] = {}

    @contextmanager
    def measure(self, stage_name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self._timings[stage_name] = (time.perf_counter() - start) * 1000.0

    def snapshot(self) -> dict[str, float]:
        return {name: round(value, 3) for name, value in self._timings.items()}
