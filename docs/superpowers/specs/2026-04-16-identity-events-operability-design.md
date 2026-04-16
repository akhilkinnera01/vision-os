# Vision OS Identity, Events, and Operability Design

## Goal

Upgrade Vision OS from frame-level scene labeling into a stateful runtime that maintains
actor identities, emits meaningful events, externalizes policy thresholds, surfaces
stage-level telemetry, and supports replay-based regression evaluation.

## Scope

This design covers:

- persistent identity tracking with stable `track_id` values
- actor-level temporal state for focus, distraction, dwell, and interaction history
- a typed event layer for scene and actor transitions
- policy-driven thresholds and weights loaded from YAML
- structured telemetry, worker health reporting, and stage timing
- replay and golden regression fixtures with deterministic event assertions

This design does not add a heavyweight multi-object tracking dependency or raw video
storage in replay artifacts. The first tracking pass will use deterministic matching
over structured detections so replay mode remains lightweight and testable.

## Architecture

The runtime stays modular and extends the existing pipeline in this order:

1. `perception.detector` returns detections without IDs.
2. `tracking.tracker` assigns stable `track_id` values using policy-driven matching.
3. `features.builder` derives frame-level spatial features from tracked detections.
4. `state.actor_store` updates per-track rolling state and emits actor summaries.
5. `state.memory` updates scene-level temporal state with policy-driven thresholds.
6. `context.rules` infers the scene context from frame features and temporal state.
7. `decision.engine` stabilizes the current scene decision.
8. `events.emitter` converts scene and actor state transitions into typed events.
9. `explain.explain` and `ui.renderer` surface events, tracks, and telemetry.
10. `runtime.io` persists tracked detections plus emitted events into replay artifacts.

This preserves the current reasoning pipeline while inserting identity and event layers
at the points where they belong, instead of folding everything into `app.py`.

## Components

### `common.models`

Extend shared models to carry identity and event information:

- `Detection.track_id: int | None`
- `Track` for active tracked entities
- `ActorState` and `ActorSummary` for per-track rolling state
- typed `VisionEvent` dataclasses with `event_type`, `timestamp`, severity, metadata
- replay payloads that store both tracked detections and emitted events
- richer runtime metrics with optional stage timing snapshots

### `tracking/`

Add a simple deterministic tracker:

- `matching.py`: IoU and center-distance helpers
- `track_store.py`: active tracks, expiry, next ID allocation
- `tracker.py`: assignment logic, creation, retention, and expiration

The tracker will match detections by label and geometry. Person tracks are the highest
value path, but the implementation should support any label so future policies can tune
which classes remain persistent.

### `state/actor_store.py`

Maintain actor-level rolling history keyed by `track_id`.

For each actor, capture:

- first seen / last seen / dwell duration
- recent labels and positions
- laptop proximity streak
- phone proximity streak
- approach / leave state
- collaboration neighbors for clustered people

This state feeds the event engine and lets explanations refer to persistent actors
instead of only aggregate scene facts.

### `events/`

Emit semantic state transitions:

- scene events: transition started, transition confirmed, focus sustained
- distraction events: started, spike, resolved
- collaboration events: group formed, collaboration increasing, group dispersed
- stability events: unstable, stabilized
- actor events: actor arrived, actor left, actor switched from laptop to phone

Event emission is reducer-based so replay mode stays deterministic. The reducer sees the
previous scene/actor state, the new scene/actor state, and emits zero or more events.

### `common.policy` and `policies/*.yaml`

Add validated policy loading. The runtime should support at least:

- `default.yaml`
- `office.yaml`
- `home.yaml`

Policies govern:

- tracking IoU / distance thresholds and track TTL
- feature distance thresholds and score weights
- temporal windows, streak sizes, and instability cutoffs
- decision hysteresis thresholds
- event confirmation durations

Invalid or incomplete policies should fail fast with readable messages.

### `telemetry/`

Add runtime operability primitives:

- `timers.py`: stage timer context and aggregate timing stats
- `logging.py`: structured JSON logger with optional plain-text fallback
- `health.py`: health state plus worker exception propagation

Telemetry should track at least these stages:

- detect
- track
- feature
- actor_state
- temporal
- context
- decision
- event
- explain
- render

### Replay Harness

Replay mode becomes a regression surface, not just a playback surface.

Add:

- deterministic replay fixtures under `tests/replays/`
- golden expectations under `tests/golden/`
- assertions for emitted events, decision sequence, stability floor, and replay latency

The fixtures should be generated from tracked detections plus typed events so CI can
verify behavior without a webcam.

## Data Flow

For each frame:

1. detect objects
2. assign stable track IDs
3. build frame-level features from tracked detections
4. update actor state
5. update temporal scene state
6. infer context and decision
7. reduce previous and current state into events
8. update telemetry
9. render overlays and persist replay/event artifacts

Replay mode skips detection and tracking work if tracked detections are already stored in
the artifact, but still runs the actor, temporal, decision, and event pipeline so
regression tests stay faithful to the logic used in live runs.

## Error Handling

- missing or invalid policy files fail on startup with a readable CLI error
- inference worker exceptions are pushed to a health queue and stop the main loop loudly
- malformed replay records fail with a targeted parsing error, not a generic traceback
- event persistence is best-effort only in the sense that a file path can be created
  automatically; serialization bugs are still fatal because silent event loss would hide
  regressions

## Testing Strategy

The implementation uses test-first changes in this order:

1. tracking unit tests for ID persistence, expiry, and reassignment
2. actor store tests for dwell and interaction state
3. event reducer tests for distraction, focus, and collaboration transitions
4. policy loader tests for valid and invalid YAML
5. telemetry tests for stage timing aggregation and worker failure propagation
6. replay golden tests for event sequence and decision stability

## Tradeoffs

### Recommended approach: deterministic in-process tracker and reducer

Pros:

- no extra runtime service or heavy tracking dependency
- deterministic replay behavior
- easy to test in CI

Cons:

- less robust than a dedicated MOT algorithm under severe occlusion

### Rejected: ByteTrack-style external dependency first

Reason:

- stronger tracking, but too much complexity for the current repo stage
- harder to keep deterministic in replay and CI without extra scaffolding

### Rejected: event logic embedded in `decision.engine`

Reason:

- would blur current-state classification with lifecycle transitions
- harder to test and extend cleanly

## Success Criteria

Vision OS should be able to say:

- the same actor stayed in focused work for multiple seconds
- an actor moved from laptop-oriented work into a phone distraction event
- a group formed and later dispersed
- replay artifacts preserve the identity and event timeline
- runtime telemetry explains where time is spent and whether the worker is healthy
