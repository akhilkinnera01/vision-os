# Vision OS

Vision OS is a modular Python system for real-time scene understanding from a webcam,
video file, or replay artifact. It uses OpenCV for capture, Ultralytics YOLO for
object detection, then layers tracking, spatial reasoning, temporal memory, event
emission, and explanation on top of those detections.

If you want the shortest possible description, it does this:

1. Detect objects in a frame
2. Track identities across frames
3. Convert detections into scene features
4. Infer context such as `Focused Work`, `Casual Use`, or `Group Activity`
5. Emit scores, events, and human-readable reasoning
6. Render everything back onto the frame

## What You See When It Runs

Vision OS overlays the live frame with:

- bounding boxes and object labels
- stable `track_id` values for tracked objects
- a scene label such as `Focused Work`
- explanation text for why that label was chosen
- live scores for focus, distraction, collaboration, and stability
- recent scene events in debug mode

This means the system is not just doing frame-by-frame object detection. It is trying
to model what is happening over time.

## Main Capabilities

- OpenCV webcam capture and video playback
- YOLO object detection through `ultralytics`
- persistent identity tracking with per-object `track_id`
- spatial signals such as person-near-laptop, person-near-phone, clustered people, and centered monitors
- temporal memory for sustained focus, distraction spikes, collaboration growth, and unstable context
- typed runtime events for transitions, distractions, collaboration changes, and stability changes
- zone-aware reasoning for named desks, benches, and room areas through `--zones-file`
- runtime profiles for workstation, study room, meeting room, lab bench, and waiting area deployments
- guided setup, saved runtime manifests, and preflight validation through `--setup`, `--config`, and `--validate-config`
- generic integrations for trigger, event, status, and session-summary publishing
- structured explanations for both compact and debug rendering
- benchmark output with FPS, latency, dropped frames, switch rate, stability score, and stage timings
- replay recording for deterministic debugging and regression testing
- structured session history and analytics exports through `--history-output` and `--session-summary-output`
- policy-driven thresholds through YAML configuration

## Repository Layout

```text
vision-os/
├── app.py
├── common/
├── perception/
├── features/
├── tracking/
├── state/
├── events/
├── context/
├── decision/
├── explain/
├── runtime/
├── telemetry/
├── zones/
├── ui/
├── policies/
├── demo/
├── docs/
└── tests/
```

## Quick Start

### 1. Create an environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The first run may download the default YOLO weights, usually `yolov8n.pt`.

### 2. Run guided setup or use the committed demo config

Guided setup:

```bash
python app.py --setup
```

Deterministic saved-config smoke test:

```bash
python app.py --config demo/demo-setup-config.yaml --max-frames 5
```

This is the shortest path from fresh clone to a validated manifest-driven run.
For the full workflow, see [docs/easy-setup.md](docs/easy-setup.md).

### 3. Try the included demo video

```bash
python app.py \
  --source video \
  --input demo/sample.mp4
```

This is the easiest way to confirm the app is wired correctly before testing a live camera.

### 4. Save a replay, benchmark, and session analytics

```bash
python app.py \
  --source video \
  --input demo/sample.mp4 \
  --record demo/demo-replay.jsonl \
  --benchmark-output demo/demo-benchmark.json \
  --history-output demo/demo-history.jsonl \
  --session-summary-output demo/demo-session-summary.json
```

### 5. Replay the exact same run in debug mode

```bash
python app.py \
  --source replay \
  --input demo/demo-replay.jsonl \
  --overlay-mode debug
```

The repo already ships these demo artifacts from the sample flow:

- `demo/sample.mp4`
- `demo/demo-setup-config.yaml`
- `demo/sample-zones.yaml`
- `demo/sample-triggers.yaml`
- `demo/sample-integrations.yaml`
- `demo/demo-replay.jsonl`
- `demo/demo-benchmark.json`
- `demo/demo-history.jsonl`
- `demo/demo-session-summary.json`
- `demo/sample-overlay.png`

Press `q` to exit any non-headless run.

## Run Modes

### Easy setup mode

Use this when you want the repo to generate and validate a starter bundle for you:

```bash
python app.py --setup
```

The guided flow writes:

- `visionos.config.yaml`
- `visionos.zones.yaml`
- `visionos.triggers.yaml`
- `visionos.integrations.yaml`

The saved config can then be reused with:

```bash
python app.py --config visionos.config.yaml
```

Useful helpers:

```bash
python app.py --list-cameras
python app.py --config visionos.config.yaml --validate-config
python app.py --demo
```

The normal runtime now prints a short startup summary so you can see which config,
source, profile, outputs, zone count, trigger count, and integration count are active
before the first frame is processed.

### Webcam mode

Use this for live scene understanding from a camera:

```bash
python app.py --source webcam --camera 0
```

Useful variants:

```bash
python app.py --source webcam --camera 0 --overlay-mode debug
python app.py --source webcam --camera 0 --record out/session.jsonl
python app.py --source webcam --camera 0 --benchmark-output out/bench.json
```

Notes:

- `--camera 0` is the default camera index
- on macOS, your terminal must have camera permission
- webcam mode uses an asynchronous inference worker and may drop frames intentionally to stay responsive

### Video mode

Use this for repeatable demos and profiling:

```bash
python app.py --source video --input path/to/video.mp4
```

Recommended when you want:

- deterministic input
- stable benchmarking
- easy replay generation
- a reproducible bug report

### Zone-aware mode

Use this when one camera should act like many virtual sensors:

```bash
python app.py \
  --source video \
  --input demo/sample.mp4 \
  --zones-file demo/sample-zones.yaml \
  --overlay-mode debug
```

With a zone file, Vision OS keeps the existing frame-level scene label and also
computes zone-local state such as `empty`, `occupied`, `solo_focus`, and
`group_activity` for each configured region.

### Profile-aware mode

Use this when the same runtime should behave like a packaged deployment type
instead of a generic scene observer:

```bash
python app.py \
  --source video \
  --input demo/sample.mp4 \
  --profile meeting_room \
  --zones-file demo/sample-zones.yaml \
  --overlay-mode debug
```

Built-in profiles currently include:

- `workstation`
- `study_room`
- `meeting_room`
- `lab_bench`
- `waiting_area`

Profiles can contribute:

- a built-in or custom policy file
- default trigger bundles
- default integration bundles
- default zones file references
- profile-scoped overlay sections

Explicit CLI flags still win. For example, `--overlay-mode debug` overrides a
profile's default overlay mode, and `--trigger-file custom.yaml` overrides a
profile's bundled trigger file.

### Triggered zone mode

Use this when stable scene states or zone events should also fan out to logs,
stdout, webhooks, file appends, or a narrow MQTT output:

```bash
python app.py \
  --source video \
  --input demo/sample.mp4 \
  --zones-file demo/sample-zones.yaml \
  --trigger-file demo/sample-triggers.yaml \
  --overlay-mode debug
```

### Integration mode

Use this when Vision OS should publish runtime outputs to external systems:

```bash
python app.py \
  --source video \
  --input demo/sample.mp4 \
  --trigger-file demo/sample-triggers.yaml \
  --integrations-file demo/sample-integrations.yaml \
  --history-output out/history.jsonl \
  --session-summary-output out/session-summary.json \
  --headless
```

See [docs/integrations.md](docs/integrations.md) for the config format and source types.

### Event history and analytics mode

Use this when you want the run to remain queryable after it ends:

```bash
python app.py \
  --source video \
  --input demo/sample.mp4 \
  --history-output out/history.jsonl \
  --session-summary-output out/session-summary.json \
  --benchmark-output out/bench.json
```

`--history-output` writes one append-only JSONL record per stable runtime result, while
`--session-summary-output` writes one session-level JSON summary with dominant label,
label durations, event counts, stability, FPS, and stage timings.

### Replay mode

Use this when you want to inspect reasoning without rerunning YOLO:

```bash
python app.py --source replay --input path/to/session.jsonl
```

Replay mode is good for:

- debugging scene decisions
- stepping through a recorded session repeatedly
- regression tests and golden fixtures
- very fast iteration because detection is already serialized

## Command Reference

### Required arguments

- `--source webcam|video|replay`
- `--input PATH` is required for `video` and `replay`
- `--config PATH` can replace the raw source flags when you want a saved manifest

### Setup and onboarding options

| Flag | Meaning |
| --- | --- |
| `--setup` | run the guided setup flow and write a starter bundle |
| `--config PATH` | load a saved setup/runtime manifest |
| `--validate-config` | run preflight validation and exit |
| `--list-cameras` | probe a small range of webcam indexes and exit |
| `--demo` | load the committed replay + profile preset |

### Detection and runtime options

| Flag | Meaning | Default |
| --- | --- | --- |
| `--camera` | OpenCV camera index | `0` |
| `--model` | YOLO weights path or model name | `yolov8n.pt` |
| `--conf` | minimum detection confidence | `0.35` |
| `--imgsz` | YOLO inference image size | `640` |
| `--device` | inference device such as `cpu`, `mps`, or `0` | auto |
| `--max-detections` | max detections rendered per frame | `25` |
| `--temporal-window` | seconds of rolling scene memory | `8.0` |

### Output and debugging options

| Flag | Meaning |
| --- | --- |
| `--overlay-mode compact|debug` | choose a lighter or fuller UI overlay |
| `--record PATH` | write replayable detections and events to JSONL |
| `--benchmark-output PATH` | write benchmark metrics to JSON |
| `--history-output PATH` | write structured runtime history records to JSONL |
| `--session-summary-output PATH` | write a session analytics summary to JSON |
| `--zones-file PATH` | load a YAML file with named polygon zones |
| `--trigger-file PATH` | load a YAML file with event trigger outputs |
| `--integrations-file PATH` | load a YAML file with generic integration targets |
| `--profile NAME` | load a built-in runtime profile |
| `--profile-file PATH` | load a custom runtime profile manifest |
| `--headless` | disable the OpenCV window |
| `--log-json` | emit structured logs to stderr |
| `--max-frames N` | stop after N processed frames |

### Policy options

| Flag | Meaning |
| --- | --- |
| `--policy default|office|home` | load a built-in policy preset |
| `--policy-file PATH` | load a custom YAML policy |

You can inspect built-in presets here:

- `policies/default.yaml`
- `policies/office.yaml`
- `policies/home.yaml`

You can inspect built-in runtime profiles here:

- `profiles/workstation.yaml`
- `profiles/study_room.yaml`
- `profiles/meeting_room.yaml`
- `profiles/lab_bench.yaml`
- `profiles/waiting_area.yaml`

## Typical Workflows

### Fast sanity check after cloning

```bash
source .venv/bin/activate
python app.py --source video --input demo/sample.mp4 --max-frames 60
```

### Smoke-test one built-in profile

```bash
source .venv/bin/activate
python app.py \
  --source video \
  --input demo/sample.mp4 \
  --profile meeting_room \
  --zones-file demo/sample-zones.yaml \
  --max-frames 60
```

### Build a replay artifact from a live webcam session

```bash
python app.py \
  --source webcam \
  --camera 0 \
  --record out/webcam-session.jsonl \
  --benchmark-output out/webcam-benchmark.json
```

### Export history and summary artifacts from the sample video

```bash
python app.py \
  --source video \
  --input demo/sample.mp4 \
  --zones-file demo/sample-zones.yaml \
  --history-output out/history.jsonl \
  --session-summary-output out/session-summary.json \
  --benchmark-output out/session-benchmark.json \
  --headless \
  --max-frames 60
```

### Inspect a previous run without using the camera or detector

```bash
python app.py \
  --source replay \
  --input out/webcam-session.jsonl \
  --overlay-mode debug
```

### Benchmark the sample video without opening a window

```bash
python app.py \
  --source video \
  --input demo/sample.mp4 \
  --headless \
  --benchmark-output out/video-benchmark.json
```

### Use a different policy preset

```bash
python app.py \
  --source video \
  --input demo/sample.mp4 \
  --policy office
```

### Use a custom policy file

```bash
python app.py \
  --source video \
  --input demo/sample.mp4 \
  --policy-file path/to/custom-policy.yaml
```

## Zone Files

Zone files are plain YAML and define named polygons in frame coordinates.

```yaml
zones:
  - id: desk_a
    name: Desk A
    type: occupancy
    polygon:
      - [40, 220]
      - [320, 220]
      - [320, 520]
      - [40, 520]
```

Supported V1 zone types:

- `occupancy`
- `activity`
- `transition`

Current zone-local labels:

- `empty`
- `occupied`
- `solo_focus`
- `group_activity`
- `casual_occupancy`

Zone transitions are emitted as typed events such as `zone_occupied`, `zone_cleared`,
`zone_focus_started`, and `zone_group_started`, and replay artifacts now persist the
serialized zone timeline for each frame.

## Trigger Files

Trigger files let you match stable runtime state or emitted events and send them to
one or more outputs.

```yaml
triggers:
  - id: focus-session
    when:
      source: decision.label
      operator: equals
      value: Focused Work
      min_duration_seconds: 300
    then:
      - type: file_append
        path: out/focus-session.jsonl
      - type: log
        event: trigger_fired
    cooldown_seconds: 600
```

Supported condition sources in the current surface:

- `decision.label`
- `decision.confidence`
- `temporal.metrics.*`
- `event.event_type` with optional `event_metadata_filters`

Supported outputs:

- structured log via `type: log`
- stdout via `type: stdout`
- file append via `type: file_append`
- HTTP webhook via `type: webhook`
- plain MQTT publish via `type: mqtt_publish`

Legacy flat event rules are still accepted for backward compatibility:

```yaml
triggers:
  - id: desk-b-clear-mqtt
    event_type: zone_cleared
    zone_id: desk_b
    mqtt_host: 127.0.0.1
    mqtt_port: 1883
    mqtt_topic: opencheckin/zones/desk_b
```

Trigger evaluation is stateful. Rules can use:

- `min_duration_seconds`
- `cooldown_seconds`
- `repeat_interval_seconds`
- `rearm_on_clear`

Trigger failures are logged and do not stop the inference loop.

## Output Files

### Replay file

When you pass `--record`, Vision OS writes a JSONL replay artifact. Each line stores
the recorded detections, emitted events, and serialized zone state for one frame so you
can rerun or inspect the reasoning path later without touching the detector.

Use replay files when you want:

- deterministic debugging
- reproducible issue reports
- faster iteration on scene logic
- regression fixtures for tests

The repository includes a committed example at `demo/demo-replay.jsonl`.

### Benchmark file

When you pass `--benchmark-output`, Vision OS writes a JSON summary with:

- `frames_processed`
- `fps`
- `average_inference_ms`
- `dropped_frames`
- `decision_switch_rate`
- `scene_stability_score`
- `stage_timings`

Full field descriptions live in [`docs/benchmark-output.md`](docs/benchmark-output.md).

The repository includes a committed example at `demo/demo-benchmark.json`.

### Session history file

When you pass `--history-output`, Vision OS writes a JSONL timeline of stable runtime
history. Each line stores the chosen scene label, confidence, recent event types,
stage timings, zone labels, and a few analytics-friendly metrics such as focus duration,
switch rate, FPS, and average inference time.

Use history files when you want:

- post-run analytics
- time-window inspection
- dashboard ingestion
- reproducible historical regressions

The repository includes a committed example at `demo/demo-history.jsonl`.
Field descriptions live in [`docs/session-history.md`](docs/session-history.md).

### Session summary file

When you pass `--session-summary-output`, Vision OS writes one JSON document with:

- dominant scene label
- label durations
- event counts
- average stability score
- focus and group-activity durations
- FPS, inference latency, and stage timings

The repository includes a committed example at `demo/demo-session-summary.json`.
Field descriptions live in [`docs/session-history.md`](docs/session-history.md).

## How the Pipeline Is Organized

The codebase is split into focused modules so each stage can evolve independently.

- `perception/detector.py`: runs YOLO and returns structured detections
- `tracking/`: assigns stable identities across nearby frames
- `features/builder.py`: converts detections and actor state into booleans and numeric signals
- `state/`: stores rolling scene memory and actor timelines
- `events/`: reduces state changes into typed runtime events
- `zones/`: loads zone maps, assigns detections, and derives zone-local reasoning state
- `context/rules.py`: maps features and temporal state to scene context
- `decision/engine.py`: produces the final scene label, action, and risk flags
- `explain/explain.py`: creates human-readable explanations
- `ui/renderer.py`: overlays detections, scores, context, and explanations on frames
- `runtime/`: owns sources, replay persistence, benchmarking, and the shared processing pipeline
- `telemetry/`: stage timing, logging, and health reporting

## Policies and Tuning

Policies let you change thresholds without editing Python modules.

Examples of values controlled by policy:

- tracking and matching thresholds
- spatial distance thresholds
- decision score weights
- event confirmation streaks
- instability cutoffs

Recommended approach:

1. Start with `default`
2. Try `office` or `home` if your environment consistently behaves differently
3. Copy a policy YAML and tune it with `--policy-file` if you need custom behavior

## Testing

Run the full test suite:

```bash
source .venv/bin/activate
pytest -q
```

Run a smaller verification pass:

```bash
source .venv/bin/activate
python -m compileall app.py common perception features context decision explain runtime state tracking events telemetry tests
```

Replay regression fixtures live under `tests/replays/`, and expected golden outputs
live under `tests/golden/`.

## Troubleshooting

### `Video input not found`

Make sure the path passed to `--input` exists and points to a real file.

### Webcam does not open

Things to check:

- the camera index is correct
- another app is not already holding the camera
- your terminal has camera permission
- try `--camera 1` if `--camera 0` is not the right device

### The app is slow

Try:

- `--model yolov8n.pt` if you switched to a heavier model
- `--imgsz 640` or lower
- `--device mps` on Apple Silicon if available
- `--headless` when you only need output artifacts
- video or replay mode for more controlled profiling

### I want richer debugging output

Use:

```bash
python app.py \
  --source replay \
  --input out/session.jsonl \
  --overlay-mode debug \
  --log-json
```

## Contributing

- default branch: `main`
- feature work should happen on branches
- tests should pass before opening a PR
- CI runs `pytest`
- contribution guide: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- security policy: [`SECURITY.md`](SECURITY.md)
