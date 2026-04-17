"""Checks for the committed demo artifacts used in docs and smoke workflows."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import yaml

from common.profile import load_profile
from integrations import load_trigger_config
from setupux import load_runtime_config_file
from zones import load_zones, select_zones_for_profile


DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"


def test_demo_replay_artifact_exists_and_has_frames() -> None:
    replay_path = DEMO_DIR / "demo-replay.jsonl"

    assert replay_path.is_file()
    first_line = replay_path.read_text(encoding="utf-8").splitlines()[0]
    payload = json.loads(first_line)

    assert payload["source_mode"] == "video"
    assert "detections" in payload
    assert "frame_shape" in payload
    assert "history_record" in payload
    assert payload["history_record"]["scene_label"]


def test_demo_benchmark_artifact_has_expected_fields() -> None:
    benchmark_path = DEMO_DIR / "demo-benchmark.json"
    payload = json.loads(benchmark_path.read_text(encoding="utf-8"))

    assert payload["frames_processed"] > 0
    assert "fps" in payload
    assert "average_inference_ms" in payload
    assert "stage_timings" in payload
    assert "detect" in payload["stage_timings"]


def test_demo_history_artifact_has_expected_fields() -> None:
    history_path = DEMO_DIR / "demo-history.jsonl"

    assert history_path.is_file()
    first_line = history_path.read_text(encoding="utf-8").splitlines()[0]
    payload = json.loads(first_line)

    assert payload["frame_index"] >= 0
    assert "scene_label" in payload
    assert "event_types" in payload
    assert "zone_labels" in payload
    assert "stage_timings" in payload


def test_demo_session_summary_artifact_has_expected_fields() -> None:
    summary_path = DEMO_DIR / "demo-session-summary.json"
    payload = json.loads(summary_path.read_text(encoding="utf-8"))

    assert payload["frames_processed"] > 0
    assert "dominant_scene_label" in payload
    assert "label_durations" in payload
    assert "event_counts" in payload
    assert "average_stability_score" in payload


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
    zones = load_zones(str(DEMO_DIR / "sample-zones.yaml"))
    scoped_zones = select_zones_for_profile(zones, active_profile=profile.profile_id)

    assert profile_path.is_file()
    assert profile.profile_id == "sample_demo"
    assert profile.zones_path == str(DEMO_DIR / "sample-zones.yaml")
    assert profile.trigger_path == str(DEMO_DIR / "sample-triggers.yaml")
    assert len(scoped_zones) >= 1


def test_demo_setup_config_exists_and_resolves_relative_assets() -> None:
    config_path = DEMO_DIR / "demo-setup-config.yaml"
    config = load_runtime_config_file(str(config_path))

    assert config_path.is_file()
    assert config.source_mode.value == "replay"
    assert config.input_path == str(DEMO_DIR / "demo-replay.jsonl")
    assert config.profile_path == str(DEMO_DIR / "sample-profile.yaml")
