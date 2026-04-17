"""Checks for the committed demo artifacts used in docs and smoke workflows."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import yaml

from common.profile import load_profile
from integrations import load_trigger_config


DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"


def test_demo_replay_artifact_exists_and_has_frames() -> None:
    replay_path = DEMO_DIR / "demo-replay.jsonl"

    assert replay_path.is_file()
    first_line = replay_path.read_text(encoding="utf-8").splitlines()[0]
    payload = json.loads(first_line)

    assert payload["source_mode"] == "video"
    assert "detections" in payload
    assert "frame_shape" in payload


def test_demo_benchmark_artifact_has_expected_fields() -> None:
    benchmark_path = DEMO_DIR / "demo-benchmark.json"
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))

    assert payload["frames_processed"] > 0
    assert "fps" in payload
    assert "average_inference_ms" in payload
    assert "stage_timings" in payload
    assert "detect" in payload["stage_timings"]


def test_demo_overlay_image_is_present_and_loadable() -> None:
    overlay_path = DEMO_DIR / "sample-overlay.png"

    assert overlay_path.is_file()
    image = cv2.imread(str(overlay_path))

    assert image is not None
    assert image.shape[0] > 0
    assert image.shape[1] > 0


def test_demo_zone_config_exists_and_has_zones() -> None:
    zone_path = DEMO_DIR / "sample-zones.yaml"
    payload = yaml.safe_load(zone_path.read_text(encoding="utf-8"))

    assert zone_path.is_file()
    assert isinstance(payload, dict)
    assert len(payload["zones"]) >= 2
    assert any(zone.get("profile") for zone in payload["zones"])


def test_demo_trigger_config_exists_and_has_rules() -> None:
    trigger_path = DEMO_DIR / "sample-triggers.yaml"
    payload = yaml.safe_load(trigger_path.read_text(encoding="utf-8"))
    config = load_trigger_config(str(trigger_path))

    assert trigger_path.is_file()
    assert isinstance(payload, dict)
    assert len(payload["triggers"]) >= 2
    assert len(config.rules) >= 2
    assert any(rule.condition and rule.condition.source == "decision.label" for rule in config.rules)


def test_demo_profile_manifest_exists_and_resolves_assets() -> None:
    profile_path = DEMO_DIR / "sample-profile.yaml"
    profile = load_profile(path=str(profile_path))

    assert profile_path.is_file()
    assert profile.profile_id == "sample_demo"
    assert profile.zones_path == str(DEMO_DIR / "sample-zones.yaml")
    assert profile.trigger_path == str(DEMO_DIR / "sample-triggers.yaml")
