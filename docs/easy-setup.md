# Easy Setup UX

Vision OS now ships with an onboarding path for first-run setup.

The goal is simple:

1. confirm the repo can run
2. save a starter config
3. validate the chosen source and runtime inputs
4. rerun from one short `--config` command

## Guided Setup

Run the guided flow from the repo root:

```bash
python app.py --setup
```

The setup flow asks for:

- where to save the starter bundle
- which source mode to use
- camera index or file path
- which built-in profile best matches the space
- which overlay mode to start with

It then writes:

- `visionos.config.yaml`
- `visionos.zones.yaml`
- `visionos.triggers.yaml`

The generated config is safe to run immediately. The zone and trigger template files
are created for later editing, but they are not enabled in the starter manifest until
you point the runtime at them.

## Camera Discovery

If you choose `webcam` during setup, Vision OS performs a quick OpenCV probe and
prints the detected camera indexes before asking which one to use.

You can also run the probe directly:

```bash
python app.py --list-cameras
```

## Validate a Saved Config

Once you have a manifest, run:

```bash
python app.py --config visionos.config.yaml --validate-config
```

The validation report checks:

- selected profile loading
- effective policy loading
- effective zones file loading when enabled
- effective trigger file loading when enabled
- source open/read health
- output directory writability
- model loading unless skipped by a custom caller

The report is designed to answer the common onboarding questions quickly:

- did my source open?
- did my profile resolve?
- are zones and triggers actually active?
- will artifacts be writable?

## Saved Config Workflow

After setup, the normal run path becomes:

```bash
python app.py --config visionos.config.yaml
```

Explicit CLI flags still override config values. For example:

```bash
python app.py \
  --config visionos.config.yaml \
  --overlay-mode debug \
  --max-frames 120
```

## Deterministic Demo Config

The repo includes one committed config manifest for setup smoke tests:

```bash
python app.py --config demo/demo-setup-config.yaml --max-frames 5
```

That manifest uses the committed replay artifact and sample profile so it works
without a live camera.

## Startup Summary

Normal runs now print a short startup summary before the main loop begins. It includes:

- which config source is active
- the source descriptor
- selected profile and policy
- overlay mode and headless state
- loaded zone and trigger counts
- which history, benchmark, and session-summary artifacts are enabled

This is meant to reduce "guess and retry" loops during onboarding and demos.
