"""Tests for StageTimer cumulative behavior."""

from __future__ import annotations

import pytest
from unittest.mock import patch
from telemetry.timers import StageTimer

def test_stage_timer_accumulates_multiple_measurements() -> None:
    timer = StageTimer()

    with patch("time.perf_counter") as mock_perf:
        # First measurement of "detect": 10ms
        mock_perf.side_effect = [0.0, 0.010]
        with timer.measure("detect"):
            pass

        # Second measurement of "detect": 20ms
        mock_perf.side_effect = [1.0, 1.020]
        with timer.measure("detect"):
            pass

        # Measurement of another stage "track": 5ms
        mock_perf.side_effect = [2.0, 2.005]
        with timer.measure("track"):
            pass

    snapshot = timer.snapshot()

    # We expect "detect" to be 10 + 20 = 30ms
    assert snapshot["detect"] == 30.0
    # We expect "track" to be 5ms
    assert snapshot["track"] == 5.0

def test_stage_timer_handles_no_measurements() -> None:
    timer = StageTimer()
    assert timer.snapshot() == {}

def test_stage_timer_rounding() -> None:
    timer = StageTimer()
    with patch("time.perf_counter") as mock_perf:
        mock_perf.side_effect = [0.0, 0.00123456]
        with timer.measure("test"):
            pass

    snapshot = timer.snapshot()
    # 0.00123456 s = 1.23456 ms, should round to 1.235
    assert snapshot["test"] == 1.235
