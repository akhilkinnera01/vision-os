"""Stage timing utilities for per-frame runtime measurement."""

from __future__ import annotations

import time
from contextlib import contextmanager


class StageTimer:
    """Collect lightweight stage timings for a single pipeline pass."""

    def __init__(self) -> None:
        self._cumulative: dict[str, float] = {}

    @contextmanager
    def measure(self, stage_name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = (time.perf_counter() - start) * 1000.0
            self._cumulative[stage_name] = self._cumulative.get(stage_name, 0.0) + duration

    def snapshot(self) -> dict[str, float]:
        return {name: round(value, 3) for name, value in self._cumulative.items()}
