# Identity, Events, and Operability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent identity tracking, typed events, policy-driven thresholds, stage telemetry, and replay regression coverage to Vision OS.

**Architecture:** Extend the existing pipeline with a deterministic tracker, actor store, event reducer, policy loader, and telemetry modules while preserving the current scene reasoning flow. Replay artifacts become a full regression surface by persisting tracked detections and event timelines.

**Tech Stack:** Python, OpenCV, Ultralytics YOLO, PyYAML, pytest

---

### Task 1: Extend shared models and policy plumbing

**Files:**
- Create: `common/policy.py`
- Create: `policies/default.yaml`
- Create: `policies/office.yaml`
- Create: `policies/home.yaml`
- Modify: `common/config.py`
- Modify: `common/models.py`
- Modify: `pyproject.toml`
- Test: `tests/test_policy.py`

- [ ] Write failing tests for policy loading, defaults, and validation.
- [ ] Add policy dataclasses and a YAML loader with clear validation errors.
- [ ] Extend shared models with `track_id`, actor state, typed events, replay envelopes, and richer runtime metrics.
- [ ] Thread policy selection through runtime config.
- [ ] Re-run policy and model tests until green.

### Task 2: Add tracking and actor state

**Files:**
- Create: `tracking/__init__.py`
- Create: `tracking/matching.py`
- Create: `tracking/track_store.py`
- Create: `tracking/tracker.py`
- Create: `state/actor_store.py`
- Modify: `features/builder.py`
- Modify: `common/models.py`
- Test: `tests/test_tracking.py`

- [ ] Write failing tests for ID persistence, track expiry, and actor dwell history.
- [ ] Implement geometry matching helpers and active track storage.
- [ ] Implement tracker assignment with policy-driven thresholds.
- [ ] Implement actor store updates and summaries for per-track interaction state.
- [ ] Update feature extraction to use tracked detections and actor summaries where useful.
- [ ] Re-run tracking and actor tests until green.

### Task 3: Add typed event emission

**Files:**
- Create: `events/__init__.py`
- Create: `events/models.py`
- Create: `events/reducer.py`
- Create: `events/emitter.py`
- Modify: `state/memory.py`
- Modify: `context/rules.py`
- Modify: `decision/engine.py`
- Modify: `explain/explain.py`
- Test: `tests/test_events.py`

- [ ] Write failing tests for distraction start/resolution, focus sustained, and group formed/dispersed.
- [ ] Implement typed event models and a reducer that compares prior and current scene/actor state.
- [ ] Integrate event emission into temporal and decision flow without coupling event lifecycle to UI.
- [ ] Surface recent events in explanation output.
- [ ] Re-run event tests until green.

### Task 4: Add telemetry and worker health

**Files:**
- Create: `telemetry/__init__.py`
- Create: `telemetry/timers.py`
- Create: `telemetry/logging.py`
- Create: `telemetry/health.py`
- Modify: `runtime/benchmark.py`
- Modify: `app.py`
- Modify: `docs/benchmark-output.md`
- Test: `tests/test_telemetry.py`

- [ ] Write failing tests for stage timing aggregation and worker exception propagation.
- [ ] Add stage timer helpers and structured logging primitives.
- [ ] Extend benchmark output to include per-stage timing summaries.
- [ ] Wire worker exception reporting into the live runtime loop.
- [ ] Re-run telemetry tests until green.

### Task 5: Persist tracked replay artifacts and build golden replay evaluation

**Files:**
- Create: `tests/replays/focused_work.jsonl`
- Create: `tests/replays/distraction_spike.jsonl`
- Create: `tests/replays/collaboration_growth.jsonl`
- Create: `tests/golden/focused_work.expected.json`
- Create: `tests/golden/distraction_spike.expected.json`
- Create: `tests/golden/collaboration_growth.expected.json`
- Modify: `runtime/io.py`
- Modify: `README.md`
- Modify: `tests/test_pipeline.py`
- Create: `tests/test_replay_regression.py`

- [ ] Write failing golden replay tests for event sequence, label sequence, and replay timing expectations.
- [ ] Extend replay recording to persist tracked detections and typed events.
- [ ] Extend replay loading to feed deterministic regression evaluation.
- [ ] Document the new replay and policy workflow in the README.
- [ ] Re-run replay regression tests until green.

### Task 6: Full verification and GitHub wrap-up

**Files:**
- Modify: `.github/workflows/ci.yml` if test discovery or new fixture paths require it

- [ ] Run targeted tests for each new subsystem.
- [ ] Run `pytest -q`.
- [ ] Run `python -m compileall app.py common perception features context decision explain runtime state tracking events telemetry tests`.
- [ ] Run a video-to-replay smoke test using the shipped `demo/sample.mp4`.
- [ ] Run replay regression tests from the recorded artifacts.
- [ ] Update the GitHub issues, push the branch, open a PR, and merge after CI passes while keeping the branch on GitHub.
