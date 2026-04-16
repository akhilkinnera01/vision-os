# Vision OS

Vision OS is a modular Python project for real-time scene understanding with a webcam.
It uses OpenCV for video capture, Ultralytics YOLO for object detection, and a small
reasoning pipeline that turns detections into scene labels such as `Focused Work`,
`Casual Use`, and `Group Activity`.

## Highlights

- Real-time webcam capture with OpenCV
- YOLO-based object detection with structured outputs
- Feature extraction layer for booleans, counts, and lightweight scores
- Rule-based scene context inference and decision engine
- Human-readable explanation generation
- UI overlays for boxes, labels, scene summary, and reasoning

## Project Layout

```text
vision-os/
├── app.py
├── common/
│   ├── config.py
│   └── models.py
├── perception/
│   └── detector.py
├── features/
│   └── builder.py
├── context/
│   └── rules.py
├── decision/
│   └── engine.py
├── explain/
│   └── explain.py
├── ui/
│   └── renderer.py
└── tests/
    └── test_pipeline.py
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

```bash
python app.py --camera 0 --model yolov8n.pt
```

Useful flags:

- `--camera`: webcam index, default `0`
- `--model`: YOLO weights, default `yolov8n.pt`
- `--conf`: detection confidence threshold
- `--imgsz`: YOLO inference size
- `--device`: optional inference device such as `cpu`, `mps`, or `0`

Press `q` to exit.

## Testing

```bash
pytest
```

## Design Notes

- The perception layer is isolated from the reasoning stack so the detector can be swapped later.
- Shared dataclasses keep modules loosely coupled and easy to test.
- Scene labels are inferred from simple heuristics that can later be replaced by learned policies.
- The renderer is intentionally separate so UI styling can evolve without touching inference logic.

## Open Source Workflow

- Default branch: `main`
- Feature work happens on short-lived branches
- Changes are reviewed through pull requests, even for solo work
- `CODEOWNERS` and templates keep contributions consistent
- CI runs `pytest` on pushes and pull requests
- Contribution guide: [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Security policy: [`SECURITY.md`](SECURITY.md)
