# Vision OS

Vision OS is a modular Python project for real-time scene understanding with a webcam,
video file, or replay artifact. It uses OpenCV for capture, Ultralytics YOLO for object
detection, and a layered reasoning pipeline that models scene state over time.

## Highlights

- Real-time webcam capture with OpenCV
- YOLO-based object detection with structured outputs
- Spatial reasoning such as person-near-laptop, person-near-phone, clustered people, and centered monitors
- Temporal scene memory for sustained focus, distraction spikes, collaboration trends, and context instability
- Structured explanations with compact and debug overlays
- Live scene scores for focus, distraction, collaboration, and stability
- Replay recording plus benchmark output for deterministic debugging

## Project Layout

```text
vision-os/
├── app.py
├── common/
├── perception/
├── features/
├── state/
├── context/
├── decision/
├── explain/
├── runtime/
├── ui/
├── docs/
└── tests/
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The first run downloads the default YOLO model weights if they are not already available.

## Run

### Mode Matrix

| Mode | Command | Use it for |
| --- | --- | --- |
| Webcam | `python app.py --source webcam --camera 0` | live monitoring |
| Video | `python app.py --source video --input path/to/file.avi` | deterministic demos |
| Replay | `python app.py --source replay --input path/to/session.jsonl --headless` | reasoning playback and debugging |

### Common Flags

- `--model`: YOLO weights path or name, default `yolov8n.pt`
- `--conf`: detection confidence threshold
- `--imgsz`: YOLO inference size
- `--device`: optional inference device such as `cpu`, `mps`, or `0`
- `--overlay-mode compact|debug`: switch UI density
- `--temporal-window`: rolling memory window in seconds
- `--record path/to/session.jsonl`: save replayable detections during webcam or video runs
- `--benchmark-output path/to/metrics.json`: emit machine-readable benchmark output
- `--max-frames N`: stop after a fixed number of frames
- `--headless`: disable the OpenCV window for replay or benchmark runs

### Example Workflows

Run the live webcam UI:

```bash
python app.py --source webcam --camera 0 --model yolov8n.pt
```

Process a local video, emit a benchmark file, and save a replay artifact:

```bash
python app.py \
  --source video \
  --input demo/sample.mp4 \
  --record demo/demo-replay.jsonl \
  --benchmark-output demo/demo-benchmark.json
```

Replay the saved detections in debug mode:

```bash
python app.py \
  --source replay \
  --input demo/demo-replay.jsonl \
  --overlay-mode debug
```

The repository includes `demo/sample.mp4` so the example above works from a fresh clone.
Generated replay and benchmark artifacts inside `demo/` are ignored by git.

Press `q` to exit non-headless runs.

## Benchmark Output

Vision OS can write benchmark metrics such as processed FPS, average inference latency,
dropped frames, and decision switch rate. The field definitions live in
[`docs/benchmark-output.md`](docs/benchmark-output.md).

## Testing

```bash
source .venv/bin/activate
pytest -q
```

## Design Notes

- `perception/` stays detection-only.
- `features/` is frame-local and spatial.
- `state/` owns rolling temporal memory and live scene metrics.
- `context/` remains stateless and maps features plus temporal state to labels.
- `decision/` owns final action selection and hysteresis.
- `explain/` and `ui/` stay presentation-focused.

## Open Source Workflow

- Default branch: `main`
- Feature work happens on short-lived branches
- Changes are reviewed through pull requests, even for solo work
- `CODEOWNERS` and templates keep contributions consistent
- CI runs `pytest` on pushes and pull requests
- Contribution guide: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Security policy: [`SECURITY.md`](SECURITY.md)
