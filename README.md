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
- structured explanations for both compact and debug rendering
- benchmark output with FPS, latency, dropped frames, switch rate, stability score, and stage timings
- replay recording for deterministic debugging and regression testing
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

### 2. Try the included demo video

```bash
python app.py \
  --source video \
  --input demo/sample.mp4
```

This is the easiest way to confirm the app is wired correctly before testing a live camera.

### 3. Save a replay and benchmark

```bash
python app.py \
  --source video \
  --input demo/sample.mp4 \
  --record demo/demo-replay.jsonl \
  --benchmark-output demo/demo-benchmark.json
```

### 4. Replay the exact same run in debug mode

```bash
python app.py \
  --source replay \
  --input demo/demo-replay.jsonl \
  --overlay-mode debug
```

The repo already ships these demo artifacts from the sample flow:

- `demo/sample.mp4`
- `demo/sample-zones.yaml`
- `demo/sample-triggers.yaml`
- `demo/demo-replay.jsonl`
- `demo/demo-benchmark.json`
- `demo/sample-overlay.png`

Press `q` to exit any non-headless run.

## Run Modes

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

### Triggered zone mode

Use this when zone events should also fan out to local logs, webhooks, or a narrow
MQTT output:

```bash
python app.py \
  --source video \
  --input demo/sample.mp4 \
  --zones-file demo/sample-zones.yaml \
  --trigger-file demo/sample-triggers.yaml \
  --overlay-mode debug
```

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
| `--zones-file PATH` | load a YAML file with named polygon zones |
| `--trigger-file PATH` | load a YAML file with event trigger outputs |
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

## Typical Workflows

### Fast sanity check after cloning

```bash
source .venv/bin/activate
python app.py --source video --input demo/sample.mp4 --max-frames 60
```

### Build a replay artifact from a live webcam session

```bash
python app.py \
  --source webcam \
  --camera 0 \
  --record out/webcam-session.jsonl \
  --benchmark-output out/webcam-benchmark.json
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

Trigger files let you match emitted events and send them to one or more outputs.

```yaml
triggers:
  - id: desk-a-focus-log
    event_type: zone_focus_started
    zone_id: desk_a
    log_path: out/zone-events.jsonl
```

Supported outputs in the current narrow surface:

- local JSONL event log via `log_path`
- HTTP webhook via `webhook_url`
- plain MQTT publish via `mqtt_host`, `mqtt_port`, and `mqtt_topic`

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
