"""Entry point for the Vision OS webcam, video, and replay runtime."""

from __future__ import annotations

import argparse
from dataclasses import replace
import queue
import sys
import threading
import time
from pathlib import Path

import cv2

from common.config import VisionOSConfig
from common.models import OverlayMode, SourceMode
from common.profile import ProfileValidationError, RuntimeProfile, load_profile
from common.policy import PolicyValidationError, load_policy
from integrations import IntegrationConfigError, IntegrationPublisher, load_integration_config, load_trigger_config
from runtime.benchmark import BenchmarkTracker
from runtime.history import HistoryRecorder, SessionAnalyticsEngine
from runtime.pipeline import InferenceOutput, VisionPipeline
from runtime.io import ReplayFrameSource, ReplayRecorder, VideoFrameSource, WebcamFrameSource
from server import (
    ArtifactIndex,
    LiveStateStore,
    SessionController,
    SessionSnapshot,
    SessionStore,
    ValidationRecord,
    ValidationStore,
    WorkspaceManifest,
    WorkspaceStore,
    RuntimeHost,
)
from server.launchpad import LaunchpadService
from server.web import LaunchpadApp, serve_launchpad
from telemetry.health import HealthMonitor
from telemetry.logging import VisionLogger
from ui.renderer import FrameRenderer
from setupux.config_file import SetupConfigError, load_runtime_config_file
from setupux.models import ValidationCheck, ValidationReport, ValidationStatus
from setupux.summary import format_startup_summary, format_validation_report
from setupux.validate import discover_camera_indexes, validate_runtime_setup
from setupux.wizard import run_setup_wizard
from zones import ZoneConfigError, load_zones, select_zones_for_profile


def parse_args() -> VisionOSConfig:
    """Parse CLI arguments into a runtime config object."""
    parser = argparse.ArgumentParser(description="Run Vision OS on a webcam, video, or replay feed.")
    argv = sys.argv[1:]
    parser.add_argument("--app", action="store_true", help="Run the local Vision OS browser app.")
    parser.add_argument("--app-host", default="127.0.0.1", help="Host interface for the local browser app.")
    parser.add_argument("--app-port", type=int, default=8765, help="Port for the local browser app.")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the local browser app automatically.")
    parser.add_argument("--config", help="Optional path to a saved Vision OS runtime config YAML file.")
    parser.add_argument("--setup", action="store_true", help="Run the guided starter config flow and exit.")
    parser.add_argument("--list-cameras", action="store_true", help="Probe a small camera index range and exit.")
    parser.add_argument("--validate-config", action="store_true", help="Run setup validation and exit.")
    parser.add_argument("--demo", action="store_true", help="Run the bundled demo preset.")
    parser.add_argument("--camera", type=int, default=0, help="OpenCV camera index.")
    parser.add_argument("--source", choices=[mode.value for mode in SourceMode], default="webcam")
    parser.add_argument("--input", help="Path to a video file or replay artifact.")
    parser.add_argument("--profile", help="Optional built-in runtime profile name.")
    parser.add_argument("--profile-file", help="Optional path to a custom runtime profile YAML file.")
    parser.add_argument("--zones-file", help="Optional path to a YAML file that defines static polygon zones.")
    parser.add_argument("--trigger-file", help="Optional path to a YAML file that defines event trigger outputs.")
    parser.add_argument("--integrations-file", help="Optional path to a YAML file that defines generic integration targets.")
    parser.add_argument("--model", default="yolov8n.pt", help="YOLO weights path or name.")
    parser.add_argument("--conf", type=float, default=0.35, help="Confidence threshold.")
    parser.add_argument("--imgsz", type=int, default=640, help="YOLO inference size.")
    parser.add_argument(
        "--device",
        default=None,
        help="Optional inference device such as cpu, mps, or 0 for CUDA.",
    )
    parser.add_argument(
        "--max-detections",
        type=int,
        default=25,
        help="Cap detections per frame to keep overlays readable.",
    )
    parser.add_argument("--record", help="Optional path to save replayable detections as JSONL.")
    parser.add_argument("--benchmark-output", help="Optional path to write benchmark metrics as JSON.")
    parser.add_argument("--history-output", help="Optional path to write structured session history as JSONL.")
    parser.add_argument("--session-summary-output", help="Optional path to write a session analytics summary as JSON.")
    parser.add_argument("--policy", default="default", help="Named policy to load from the policies/ directory.")
    parser.add_argument("--policy-file", help="Optional path to a custom policy YAML file.")
    parser.add_argument(
        "--overlay-mode",
        choices=[mode.value for mode in OverlayMode],
        default=OverlayMode.COMPACT.value,
        help="Choose compact or debug overlay rendering.",
    )
    parser.add_argument(
        "--temporal-window",
        type=float,
        default=8.0,
        help="Rolling temporal window in seconds for scene memory.",
    )
    parser.add_argument("--max-frames", type=int, default=None, help="Stop after N frames.")
    parser.add_argument("--headless", action="store_true", help="Disable OpenCV window rendering.")
    parser.add_argument("--log-json", action="store_true", help="Emit structured JSON logs to stderr.")
    args = parser.parse_args()

    if args.config and args.demo:
        parser.error("--config and --demo cannot be used together.")
    if args.setup and (args.config or args.demo):
        parser.error("--setup cannot be combined with --config or --demo.")

    if args.config:
        config_from_file = load_runtime_config_file(args.config)
    elif args.demo:
        config_from_file = _demo_runtime_config()
    else:
        config_from_file = VisionOSConfig()

    source_mode = SourceMode(args.source) if "--source" in argv else config_from_file.source_mode
    input_path = args.input if "--input" in argv else config_from_file.input_path
    if source_mode in {SourceMode.VIDEO, SourceMode.REPLAY} and not args.input:
        if input_path is None:
            parser.error("--input is required for video and replay modes.")

    return VisionOSConfig(
        config_path=args.config if args.config else config_from_file.config_path,
        app_mode=args.app,
        app_host=args.app_host if "--app-host" in argv else config_from_file.app_host,
        app_port=args.app_port if "--app-port" in argv else config_from_file.app_port,
        open_browser=(not args.no_browser) if "--no-browser" in argv else config_from_file.open_browser,
        setup_mode=args.setup,
        list_cameras=args.list_cameras,
        validate_config=args.validate_config,
        demo_mode=args.demo or config_from_file.demo_mode,
        camera_index=args.camera if "--camera" in argv else config_from_file.camera_index,
        model_name=args.model if "--model" in argv else config_from_file.model_name,
        confidence_threshold=args.conf if "--conf" in argv else config_from_file.confidence_threshold,
        image_size=args.imgsz if "--imgsz" in argv else config_from_file.image_size,
        device=args.device if "--device" in argv else config_from_file.device,
        max_detections=args.max_detections if "--max-detections" in argv else config_from_file.max_detections,
        source_mode=source_mode,
        input_path=input_path,
        profile_name=args.profile if "--profile" in argv else config_from_file.profile_name,
        profile_path=args.profile_file if "--profile-file" in argv else config_from_file.profile_path,
        zones_path=args.zones_file if "--zones-file" in argv else config_from_file.zones_path,
        trigger_path=args.trigger_file if "--trigger-file" in argv else config_from_file.trigger_path,
        integrations_path=(
            args.integrations_file if "--integrations-file" in argv else config_from_file.integrations_path
        ),
        record_path=args.record if "--record" in argv else config_from_file.record_path,
        benchmark_output_path=(
            args.benchmark_output if "--benchmark-output" in argv else config_from_file.benchmark_output_path
        ),
        history_output_path=args.history_output if "--history-output" in argv else config_from_file.history_output_path,
        session_summary_output_path=(
            args.session_summary_output
            if "--session-summary-output" in argv
            else config_from_file.session_summary_output_path
        ),
        policy_name=args.policy if "--policy" in argv else config_from_file.policy_name,
        policy_path=args.policy_file if "--policy-file" in argv else config_from_file.policy_path,
        overlay_mode=OverlayMode(args.overlay_mode) if "--overlay-mode" in argv else config_from_file.overlay_mode,
        temporal_window_seconds=(
            args.temporal_window if "--temporal-window" in argv else config_from_file.temporal_window_seconds
        ),
        max_frames=args.max_frames if "--max-frames" in argv else config_from_file.max_frames,
        headless=args.headless if "--headless" in argv else config_from_file.headless,
        log_json=args.log_json if "--log-json" in argv else config_from_file.log_json,
        policy_explicit=(("--policy" in argv) or ("--policy-file" in argv)) or config_from_file.policy_explicit,
        zones_explicit=("--zones-file" in argv) or config_from_file.zones_explicit,
        trigger_explicit=("--trigger-file" in argv) or config_from_file.trigger_explicit,
        integrations_explicit=("--integrations-file" in argv) or config_from_file.integrations_explicit,
        overlay_mode_explicit=("--overlay-mode" in argv) or config_from_file.overlay_mode_explicit,
    )


def _demo_runtime_config() -> VisionOSConfig:
    """Return the bundled demo preset as a config-like default set."""
    demo_dir = Path(__file__).resolve().parent / "demo"
    return VisionOSConfig(
        demo_mode=True,
        source_mode=SourceMode.REPLAY,
        input_path=str(demo_dir / "demo-replay.jsonl"),
        profile_path=str(demo_dir / "sample-profile.yaml"),
        overlay_mode=OverlayMode.DEBUG,
    )


def _queue_latest(frame_queue: queue.Queue, item) -> bool:
    """Keep only the newest item so slow inference does not build latency."""
    dropped = False
    try:
        frame_queue.put_nowait(item)
    except queue.Full:
        try:
            frame_queue.get_nowait()
            dropped = True
        except queue.Empty:
            pass
        frame_queue.put_nowait(item)
    return dropped


def _build_source(config: VisionOSConfig):
    """Construct the configured frame source."""
    if config.source_mode == SourceMode.WEBCAM:
        return WebcamFrameSource(config.camera_index)
    if config.source_mode == SourceMode.VIDEO:
        return VideoFrameSource(config.input_path or "")
    return ReplayFrameSource(config.input_path or "")


def _apply_profile_defaults(config: VisionOSConfig, profile: RuntimeProfile) -> VisionOSConfig:
    """Fill unresolved runtime settings from a selected profile while preserving explicit flags."""
    resolved = config
    if not resolved.policy_explicit:
        if profile.policy_path is not None:
            resolved = replace(resolved, policy_path=profile.policy_path)
        else:
            resolved = replace(resolved, policy_name=profile.policy_name)
    if not resolved.zones_explicit and profile.zones_path is not None:
        resolved = replace(resolved, zones_path=profile.zones_path)
    if not resolved.trigger_explicit and profile.trigger_path is not None:
        resolved = replace(resolved, trigger_path=profile.trigger_path)
    if not resolved.integrations_explicit and profile.integrations_path is not None:
        resolved = replace(resolved, integrations_path=profile.integrations_path)
    if not resolved.overlay_mode_explicit:
        resolved = replace(resolved, overlay_mode=profile.presentation.overlay_mode)
    return resolved


def _load_selected_profile(config: VisionOSConfig) -> RuntimeProfile | None:
    """Load the requested runtime profile when the operator selected one."""
    if config.profile_name is None and config.profile_path is None:
        return None
    return load_profile(name=config.profile_name, path=config.profile_path)


def _validate_input_path(config: VisionOSConfig) -> None:
    """Fail fast with a readable CLI error when file-backed inputs are missing."""
    if config.source_mode in {SourceMode.VIDEO, SourceMode.REPLAY}:
        input_path = Path(config.input_path or "")
        if not input_path.is_file():
            source_name = "video" if config.source_mode == SourceMode.VIDEO else "replay"
            raise FileNotFoundError(f"{source_name.capitalize()} input not found: {input_path}")

    if config.zones_path:
        zones_path = Path(config.zones_path)
        if not zones_path.is_file():
            raise FileNotFoundError(f"Zone config not found: {zones_path}")
    if config.trigger_path:
        trigger_path = Path(config.trigger_path)
        if not trigger_path.is_file():
            raise FileNotFoundError(f"Trigger config not found: {trigger_path}")
    if config.integrations_path:
        integrations_path = Path(config.integrations_path)
        if not integrations_path.is_file():
            raise FileNotFoundError(f"Integration config not found: {integrations_path}")


def _build_workspace_manifest(config: VisionOSConfig, *, profile_id: str | None) -> WorkspaceManifest:
    """Build a product-facing workspace record from the current CLI config."""
    workspace_key = profile_id or config.source_mode.value
    source_ref = str(config.camera_index) if config.source_mode == SourceMode.WEBCAM else config.input_path
    return WorkspaceManifest(
        workspace_id=f"{workspace_key}-{config.source_mode.value}",
        name=(profile_id or f"{config.source_mode.value.title()} Workspace").replace("_", " ").title(),
        source_mode=config.source_mode.value,
        config_path=config.config_path,
        profile_id=profile_id,
        profile_path=config.profile_path,
        policy_name=config.policy_name,
        policy_path=config.policy_path,
        source_ref=source_ref,
        zones_path=config.zones_path,
        triggers_path=config.trigger_path,
        integrations_path=config.integrations_path,
        outputs=ArtifactIndex(
            replay_path=config.record_path,
            history_path=config.history_output_path,
            benchmark_path=config.benchmark_output_path,
            session_summary_path=config.session_summary_output_path,
        ),
    )


def _server_state_dir() -> Path:
    """Return the default local browser-app state directory."""
    return Path.cwd() / ".visionos"


def _workspace_store(state_dir: Path | None = None) -> WorkspaceStore:
    """Build the file-backed workspace catalog store."""
    base_dir = _server_state_dir() if state_dir is None else state_dir
    return WorkspaceStore(base_dir / "workspaces.json")


def _session_store(state_dir: Path | None = None) -> SessionStore:
    """Build the file-backed recent-session store."""
    base_dir = _server_state_dir() if state_dir is None else state_dir
    return SessionStore(base_dir / "sessions.json")


def _validation_store(state_dir: Path | None = None) -> ValidationStore:
    """Build the file-backed validation summary store."""
    base_dir = _server_state_dir() if state_dir is None else state_dir
    return ValidationStore(base_dir / "validations.json")


def _live_state_store(state_dir: Path | None = None) -> LiveStateStore:
    """Build the file-backed live workspace store."""
    base_dir = _server_state_dir() if state_dir is None else state_dir
    return LiveStateStore(base_dir / "live")


def _build_launchpad_service(state_dir: Path | None = None, runtime_host: RuntimeHost | None = None) -> LaunchpadService:
    """Assemble the local browser app service from the default state stores."""
    return LaunchpadService(
        _workspace_store(state_dir),
        _session_store(state_dir),
        _validation_store(state_dir),
        runtime_host=runtime_host,
    )


def _write_live_session_state(
    store: LiveStateStore,
    *,
    session_id: str,
    workspace_id: str,
    packet,
    output: InferenceOutput,
    renderer: FrameRenderer,
) -> None:
    """Persist the latest live snapshot and preview frame for the browser workspace."""
    snapshot = SessionSnapshot(
        session_id=session_id,
        workspace_id=workspace_id,
        state="running",
        scene_label=output.decision.label.value,
        explanation=output.explanation.compact_summary,
        metrics={
            "fps": output.runtime_metrics.fps,
            "average_inference_ms": output.runtime_metrics.average_inference_ms,
            "focus_score": output.decision.scene_metrics.focus_score,
            "distraction_score": output.decision.scene_metrics.distraction_score,
            "collaboration_score": output.decision.scene_metrics.collaboration_score,
            "stability_score": output.decision.scene_metrics.stability_score,
            "recent_triggers": list(output.explanation.recent_triggers),
            "recent_integrations": [record.integration_id for record in output.integration_records],
            "zone_labels": {zone_state.zone_id: zone_state.context.label.value for zone_state in output.zone_states},
        },
        recent_events=tuple(output.explanation.recent_events),
        warnings=tuple(output.explanation.risk_flags),
        active_zone_ids=tuple(zone_state.zone_id for zone_state in output.zone_states),
    )
    store.save_snapshot(snapshot)
    preview = renderer.render(
        packet.frame,
        output.detections,
        output.decision,
        output.explanation,
        output.runtime_metrics,
        output.zone_states,
    )
    encoded, payload = cv2.imencode(".jpg", preview)
    if encoded:
        store.save_preview(payload.tobytes())


def run_local_app(config: VisionOSConfig) -> int:
    """Run the local browser app shell until the operator stops it."""
    runtime_host = RuntimeHost(app_path=Path(__file__).resolve())
    app = LaunchpadApp(
        _build_launchpad_service(runtime_host=runtime_host),
        live_state_store=_live_state_store(),
    )
    return serve_launchpad(app, host=config.app_host, port=config.app_port, open_browser=config.open_browser)


def _persist_workspace_manifest(config: VisionOSConfig, *, profile_id: str | None) -> WorkspaceManifest:
    """Save the current workspace manifest so the Launchpad can surface it later."""
    workspace = _build_workspace_manifest(config, profile_id=profile_id)
    _workspace_store().save_workspace(workspace)
    return workspace


def _persist_validation_report(workspace_id: str, report: ValidationReport) -> None:
    """Store the latest validation status for Launchpad health cards."""
    summary = "Validation finished without detailed checks."
    status = ValidationStatus.SKIPPED.value
    if report.checks:
        summary = report.checks[0].detail
        if any(check.status == ValidationStatus.ERROR for check in report.checks):
            status = ValidationStatus.ERROR.value
            summary = next(check.detail for check in report.checks if check.status == ValidationStatus.ERROR)
        elif any(check.status == ValidationStatus.OK for check in report.checks):
            status = ValidationStatus.OK.value
            summary = next(check.detail for check in report.checks if check.status == ValidationStatus.OK)

    _validation_store().save_result(
        ValidationRecord(
            workspace_id=workspace_id,
            status=status,
            checked_at=time.time(),
            summary=summary,
        )
    )


def _log_run_started(
    config: VisionOSConfig,
    policy_name: str,
    zone_count: int,
    logger: VisionLogger,
    *,
    profile_id: str | None = None,
) -> None:
    """Emit one structured record that captures the active runtime configuration."""
    logger.log(
        "run_started",
        mode=config.source_mode.value,
        policy=policy_name,
        profile=profile_id,
        zone_count=zone_count,
        overlay_mode=config.overlay_mode.value,
        headless=config.headless,
        temporal_window_seconds=config.temporal_window_seconds,
        zones_path=config.zones_path,
        trigger_path=config.trigger_path,
        integrations_path=config.integrations_path,
        record_path=config.record_path,
        benchmark_output_path=config.benchmark_output_path,
        history_output_path=config.history_output_path,
        session_summary_output_path=config.session_summary_output_path,
    )


def _finalize_run(
    config: VisionOSConfig,
    benchmark_tracker: BenchmarkTracker,
    logger: VisionLogger,
    *,
    analytics_engine: SessionAnalyticsEngine | None = None,
    integration_publisher: IntegrationPublisher | None = None,
) -> int:
    """Persist run artifacts, emit completion logs, and print the benchmark summary."""
    if config.record_path and config.source_mode != SourceMode.REPLAY:
        logger.log("artifact_written", kind="replay", path=config.record_path, mode=config.source_mode.value)

    if config.history_output_path:
        logger.log("artifact_written", kind="history", path=config.history_output_path, mode=config.source_mode.value)

    if config.benchmark_output_path:
        benchmark_tracker.write_summary(config.benchmark_output_path)
        logger.log("artifact_written", kind="benchmark", path=config.benchmark_output_path, mode=config.source_mode.value)

    summary = benchmark_tracker.summary()
    analytics_summary = None
    if analytics_engine is not None and hasattr(analytics_engine, "build_summary"):
        analytics_summary = analytics_engine.build_summary(summary)
    if config.session_summary_output_path and analytics_engine is not None:
        written_summary = analytics_engine.write_summary(config.session_summary_output_path, summary)
        logger.log(
            "artifact_written",
            kind="session_summary",
            path=config.session_summary_output_path,
            mode=config.source_mode.value,
        )
        if analytics_summary is None:
            analytics_summary = written_summary
    logger.log(
        "run_completed",
        mode=config.source_mode.value,
        frames=summary.frames_processed,
        fps=summary.fps,
        average_inference_ms=summary.average_inference_ms,
        dropped_frames=summary.dropped_frames,
        decision_switch_rate=summary.decision_switch_rate,
        scene_stability_score=summary.scene_stability_score,
        dominant_scene_label=None if analytics_summary is None else analytics_summary.dominant_scene_label,
        total_event_count=None if analytics_summary is None else sum(analytics_summary.event_counts.values()),
        focus_duration_seconds=None if analytics_summary is None else analytics_summary.focus_duration_seconds,
    )
    if analytics_summary is not None and integration_publisher is not None:
        integration_publisher.publish_session_summary(analytics_summary)
    print(f"Benchmark summary: {summary.to_dict()}")
    return 0


def _should_use_streaming_runtime(config: VisionOSConfig) -> bool:
    """Webcam mode stays on the real-time worker path even when rendering is disabled."""
    return config.source_mode == SourceMode.WEBCAM


def _run_streaming_mode(
    config: VisionOSConfig,
    policy,
    zones,
    trigger_config,
    source,
    renderer: FrameRenderer,
    logger: VisionLogger,
    integration_config=None,
    profile_id: str | None = None,
    session_id: str | None = None,
    workspace_id: str | None = None,
    live_state_store: LiveStateStore | None = None,
) -> int:
    """Run webcam mode with an asynchronous inference worker for responsive UI."""
    if not source.is_opened():
        logger.log("source_open_failed", mode=config.source_mode.value, input_path=config.input_path, camera=config.camera_index)
        print(f"Unable to open {config.source_mode.value} source.", file=sys.stderr)
        source.close()
        return 1

    benchmark_tracker = BenchmarkTracker()
    analytics_engine = SessionAnalyticsEngine()
    health_monitor = HealthMonitor()
    recorder = (
        ReplayRecorder(config.record_path, config.source_mode)
        if config.record_path and config.source_mode != SourceMode.REPLAY
        else None
    )
    history_recorder = HistoryRecorder(config.history_output_path) if config.history_output_path else None
    integration_publisher = (
        IntegrationPublisher(
            integration_config,
            source_mode=config.source_mode.value,
            profile_id=profile_id,
            logger=logger,
        )
        if integration_config is not None
        else None
    )

    frame_queue: queue.Queue = queue.Queue(maxsize=1)
    result_queue: queue.Queue = queue.Queue(maxsize=1)
    stop_event = threading.Event()

    def inference_worker() -> None:
        pipeline = VisionPipeline(
            config,
            policy=policy,
            zones=tuple(zones),
            trigger_config=trigger_config,
            integration_config=integration_config,
            profile_id=profile_id,
            integration_publisher=integration_publisher,
            benchmark_tracker=benchmark_tracker,
        )
        while not stop_event.is_set():
            try:
                packet = frame_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                output = pipeline.process(packet)
                history_record = getattr(output, "history_record", None)
                integration_records = getattr(output, "integration_records", ())
                if recorder is not None:
                    recorder.write(
                        frame_index=packet.frame_index,
                        timestamp=packet.timestamp,
                        frame_shape=packet.frame.shape[:2],
                        detections=output.detections,
                        events=output.events,
                        zone_states=output.zone_states,
                        trigger_records=output.trigger_records,
                        integration_records=integration_records,
                        history_record=history_record,
                    )
                if history_record is not None:
                    analytics_engine.add_record(history_record)
                    if history_recorder is not None:
                        history_recorder.write(history_record)
                if live_state_store is not None and session_id is not None and workspace_id is not None:
                    _write_live_session_state(
                        live_state_store,
                        session_id=session_id,
                        workspace_id=workspace_id,
                        packet=packet,
                        output=output,
                        renderer=renderer,
                    )
                _queue_latest(result_queue, output)
            except Exception as exc:  # pragma: no cover - exercised in runtime
                health_monitor.report_exception("pipeline", exc)
                stop_event.set()
                return

    worker = threading.Thread(target=inference_worker, name="vision-os-inference", daemon=True)
    worker.start()
    latest_output: InferenceOutput | None = None
    processed_frames = 0

    try:
        while True:
            health_monitor.raise_if_unhealthy()
            packet = source.read()
            if packet is None:
                break
            if _queue_latest(frame_queue, packet):
                benchmark_tracker.note_dropped_frame()

            try:
                while True:
                    latest_output = result_queue.get_nowait()
            except queue.Empty:
                pass

            if not config.headless:
                annotated_frame = packet.frame
                if latest_output is not None:
                    annotated_frame = renderer.render(
                        packet.frame,
                        latest_output.detections,
                        latest_output.decision,
                        latest_output.explanation,
                        latest_output.runtime_metrics,
                        latest_output.zone_states,
                    )

                cv2.imshow("Vision OS", annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            processed_frames += 1
            if config.max_frames is not None and processed_frames >= config.max_frames:
                break
    finally:
        stop_event.set()
        worker.join(timeout=1.0)
        health_monitor.raise_if_unhealthy()
        source.close()
        if recorder is not None:
            recorder.close()
        if history_recorder is not None:
            history_recorder.close()
        if live_state_store is not None:
            live_state_store.clear()
        if not config.headless:
            cv2.destroyAllWindows()

    return _finalize_run(
        config,
        benchmark_tracker,
        logger,
        analytics_engine=analytics_engine,
        integration_publisher=integration_publisher,
    )


def _run_sequential_mode(
    config: VisionOSConfig,
    policy,
    zones,
    trigger_config,
    source,
    renderer: FrameRenderer,
    logger: VisionLogger,
    integration_config=None,
    profile_id: str | None = None,
    session_id: str | None = None,
    workspace_id: str | None = None,
    live_state_store: LiveStateStore | None = None,
) -> int:
    """Run video or replay modes deterministically without dropping frames."""
    if not source.is_opened():
        logger.log("source_open_failed", mode=config.source_mode.value, input_path=config.input_path)
        print(f"Unable to open {config.source_mode.value} source.", file=sys.stderr)
        source.close()
        return 1

    benchmark_tracker = BenchmarkTracker()
    analytics_engine = SessionAnalyticsEngine()
    recorder = (
        ReplayRecorder(config.record_path, config.source_mode)
        if config.record_path and config.source_mode != SourceMode.REPLAY
        else None
    )
    history_recorder = HistoryRecorder(config.history_output_path) if config.history_output_path else None
    integration_publisher = (
        IntegrationPublisher(
            integration_config,
            source_mode=config.source_mode.value,
            profile_id=profile_id,
            logger=logger,
        )
        if integration_config is not None
        else None
    )
    pipeline = VisionPipeline(
        config,
        policy=policy,
        zones=tuple(zones),
        trigger_config=trigger_config,
        integration_config=integration_config,
        profile_id=profile_id,
        integration_publisher=integration_publisher,
        benchmark_tracker=benchmark_tracker,
    )

    processed_frames = 0
    try:
        while True:
            packet = source.read()
            if packet is None:
                break
            output = pipeline.process(packet)
            history_record = getattr(output, "history_record", None)
            integration_records = getattr(output, "integration_records", ())
            if recorder is not None:
                recorder.write(
                    frame_index=packet.frame_index,
                    timestamp=packet.timestamp,
                    frame_shape=packet.frame.shape[:2],
                    detections=output.detections,
                    events=output.events,
                    zone_states=output.zone_states,
                    trigger_records=output.trigger_records,
                    integration_records=integration_records,
                    history_record=history_record,
                )
            if history_record is not None:
                analytics_engine.add_record(history_record)
                if history_recorder is not None:
                    history_recorder.write(history_record)
            if live_state_store is not None and session_id is not None and workspace_id is not None:
                _write_live_session_state(
                    live_state_store,
                    session_id=session_id,
                    workspace_id=workspace_id,
                    packet=packet,
                    output=output,
                    renderer=renderer,
                )
            processed_frames += 1

            if not config.headless:
                annotated = renderer.render(
                    packet.frame,
                    output.detections,
                    output.decision,
                    output.explanation,
                    output.runtime_metrics,
                    output.zone_states,
                )
                cv2.imshow("Vision OS", annotated)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if config.max_frames is not None and processed_frames >= config.max_frames:
                break
    finally:
        source.close()
        if recorder is not None:
            recorder.close()
        if history_recorder is not None:
            history_recorder.close()
        if live_state_store is not None:
            live_state_store.clear()
        if not config.headless:
            cv2.destroyAllWindows()

    return _finalize_run(
        config,
        benchmark_tracker,
        logger,
        analytics_engine=analytics_engine,
        integration_publisher=integration_publisher,
    )


def main() -> int:
    """Run the end-to-end source loop until the user quits or the source is exhausted."""
    try:
        config = parse_args()
        if config.app_mode:
            return run_local_app(config)
        if config.setup_mode:
            run_setup_wizard()
            return 0
        if config.list_cameras:
            cameras = discover_camera_indexes()
            if cameras:
                print("Available cameras: " + ", ".join(str(index) for index in cameras))
            else:
                print("Available cameras: none detected")
            return 0
        if config.validate_config:
            profile = _load_selected_profile(config)
            if profile is not None:
                config = _apply_profile_defaults(config, profile)
            report = validate_runtime_setup(config)
            workspace = _persist_workspace_manifest(
                config,
                profile_id=None if profile is None else profile.profile_id,
            )
            _persist_validation_report(workspace.workspace_id, report)
            print(format_validation_report(report))
            return 0
        profile = _load_selected_profile(config)
        if profile is not None:
            config = _apply_profile_defaults(config, profile)
        _validate_input_path(config)
        policy = load_policy(name=config.policy_name, path=config.policy_path)
        zones = load_zones(config.zones_path) if config.zones_path else ()
        zones = select_zones_for_profile(
            zones,
            active_profile=None if profile is None else profile.profile_id,
        )
        trigger_config = load_trigger_config(config.trigger_path) if config.trigger_path else None
        integration_config = load_integration_config(config.integrations_path) if config.integrations_path else None
        logger = VisionLogger(config.log_json)
        renderer = FrameRenderer(
            config.overlay_mode,
            presentation=None if profile is None else getattr(profile, "presentation", None),
        )
        source = _build_source(config)
    except (
        FileNotFoundError,
        PolicyValidationError,
        ProfileValidationError,
        IntegrationConfigError,
        ZoneConfigError,
        SetupConfigError,
        ValueError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    trigger_count = 0 if trigger_config is None else len(getattr(trigger_config, "rules", ()))
    integration_count = (
        0
        if integration_config is None
        else sum(1 for target in getattr(integration_config, "targets", ()) if getattr(target, "enabled", True))
    )
    print(
        format_startup_summary(
            config,
            policy_name=policy.name,
            zone_count=len(zones),
            trigger_count=trigger_count,
            integration_count=integration_count,
            profile_id=None if profile is None else profile.profile_id,
        )
    )
    _log_run_started(config, policy.name, len(zones), logger, profile_id=None if profile is None else profile.profile_id)
    session_controller = SessionController()
    workspace = _persist_workspace_manifest(config, profile_id=None if profile is None else profile.profile_id)
    running_session = session_controller.start_session(workspace)
    live_state_store = _live_state_store()
    try:
        if _should_use_streaming_runtime(config):
            result = _run_streaming_mode(
                config,
                policy,
                zones,
                trigger_config,
                source,
                renderer,
                logger,
                integration_config=integration_config,
                profile_id=None if profile is None else profile.profile_id,
                session_id=running_session.session_id,
                workspace_id=workspace.workspace_id,
                live_state_store=live_state_store,
            )
        else:
            result = _run_sequential_mode(
                config,
                policy,
                zones,
                trigger_config,
                source,
                renderer,
                logger,
                integration_config=integration_config,
                profile_id=None if profile is None else profile.profile_id,
                session_id=running_session.session_id,
                workspace_id=workspace.workspace_id,
                live_state_store=live_state_store,
            )
    finally:
        final_state = "completed" if "result" in locals() and result == 0 else "failed"
        completed_session = session_controller.finish_session(final_state)
        _session_store().append_session(completed_session)

    return result


if __name__ == "__main__":
    raise SystemExit(main())
