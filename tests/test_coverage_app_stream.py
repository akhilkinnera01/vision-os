import queue
import threading
from unittest.mock import MagicMock, patch

import pytest

from app import _run_sequential_mode, _run_streaming_mode
from common.config import VisionOSConfig
from common.models import SourceMode
from telemetry.health import WorkerFailure

@patch('app.VisionPipeline')
@patch('app.ReplayRecorder')
@patch('cv2.imshow')
@patch('cv2.waitKey')
@patch('cv2.destroyAllWindows')
def test_run_streaming_mode_real_worker(mock_destroy, mock_wait, mock_imshow, mock_recorder, mock_pipeline):
    config = VisionOSConfig(source_mode=SourceMode.WEBCAM, headless=False, max_frames=2, record_path="out.jsonl")
    source = MagicMock()
    source.is_opened.return_value = True

    packet = MagicMock()
    packet.frame_index = 1
    packet.timestamp = 0.1
    packet.frame = MagicMock()
    packet.frame.shape = (480, 640, 3)
    source.read.side_effect = [packet, packet, None]

    pipeline_instance = MagicMock()
    output = MagicMock()
    output.detections = []
    output.events = []
    pipeline_instance.process.return_value = output
    mock_pipeline.return_value = pipeline_instance

    mock_wait.return_value = ord('q')

    with patch('app._finalize_run', return_value=0) as mock_finalize:
        assert _run_streaming_mode(config, None, source, MagicMock(), MagicMock()) == 0

@patch('app.VisionPipeline')
@patch('app.ReplayRecorder')
@patch('cv2.imshow')
@patch('cv2.waitKey')
@patch('cv2.destroyAllWindows')
def test_run_streaming_mode_exception(mock_destroy, mock_wait, mock_imshow, mock_recorder, mock_pipeline):
    config = VisionOSConfig(source_mode=SourceMode.WEBCAM, headless=False, max_frames=5)
    source = MagicMock()
    source.is_opened.return_value = True

    packet = MagicMock()
    source.read.side_effect = [packet, packet, packet, None]

    pipeline_instance = MagicMock()
    pipeline_instance.process.side_effect = Exception("Boom")
    mock_pipeline.return_value = pipeline_instance

    mock_wait.return_value = -1

    with pytest.raises(WorkerFailure, match="Worker failed during pipeline: Boom"):
        _run_streaming_mode(config, None, source, MagicMock(), MagicMock())

@patch('app.VisionPipeline')
@patch('app.ReplayRecorder')
@patch('threading.Thread')
def test_run_streaming_mode_empty_queue(mock_thread, mock_recorder, mock_pipeline):
    config = VisionOSConfig(source_mode=SourceMode.WEBCAM, headless=True, max_frames=1)
    source = MagicMock()
    source.is_opened.return_value = True

    packet = MagicMock()
    source.read.side_effect = [packet, None]

    captured_target = []
    def fake_thread_init(*args, **kwargs):
        captured_target.append(kwargs.get('target'))
        class FakeThread:
            def start(self):
                pass
            def join(self, timeout): pass
        return FakeThread()

    mock_thread.side_effect = fake_thread_init

    with patch('app._finalize_run', return_value=0):
        _run_streaming_mode(config, None, source, MagicMock(), MagicMock())

def test_run_sequential_mode_loops():
    config = VisionOSConfig(source_mode=SourceMode.VIDEO, headless=False, max_frames=2, record_path="out.jsonl")
    source = MagicMock()
    source.is_opened.return_value = True

    packet = MagicMock()
    packet.frame_index = 1
    packet.timestamp = 0.1
    packet.frame = MagicMock()
    packet.frame.shape = (480, 640, 3)

    source.read.side_effect = [packet, packet, None]

    pipeline_instance = MagicMock()
    output = MagicMock()
    output.detections = []
    output.events = []
    pipeline_instance.process.return_value = output

    renderer = MagicMock()
    logger = MagicMock()

    with patch('app.VisionPipeline', return_value=pipeline_instance), \
         patch('app.ReplayRecorder'), \
         patch('cv2.imshow'), \
         patch('cv2.waitKey', return_value=ord('q')), \
         patch('cv2.destroyAllWindows'), \
         patch('app._finalize_run', return_value=0):

        assert _run_sequential_mode(config, None, source, renderer, logger) == 0

def test_run_sequential_mode_headless():
    config = VisionOSConfig(source_mode=SourceMode.VIDEO, headless=True, max_frames=1)
    source = MagicMock()
    source.is_opened.return_value = True

    packet = MagicMock()
    packet.frame = MagicMock()
    packet.frame.shape = (480, 640, 3)
    source.read.side_effect = [packet, packet, None]

    pipeline_instance = MagicMock()
    output = MagicMock()
    output.detections = []
    output.events = []
    pipeline_instance.process.return_value = output

    with patch('app.VisionPipeline', return_value=pipeline_instance), \
         patch('app._finalize_run', return_value=0):

        assert _run_sequential_mode(config, None, source, MagicMock(), MagicMock()) == 0

def test_run_sequential_mode_source_fail():
    config = VisionOSConfig(source_mode=SourceMode.VIDEO)
    source = MagicMock()
    source.is_opened.return_value = False
    logger = MagicMock()
    assert _run_sequential_mode(config, None, source, MagicMock(), logger) == 1

def test_run_sequential_mode_end_of_source():
    config = VisionOSConfig(source_mode=SourceMode.VIDEO, headless=True)
    source = MagicMock()
    source.is_opened.return_value = True

    source.read.side_effect = [None]

    with patch('app.VisionPipeline'), \
         patch('app._finalize_run', return_value=0):

        assert _run_sequential_mode(config, None, source, MagicMock(), MagicMock()) == 0

def test_streaming_mode_renderer_with_output():
    config = VisionOSConfig(source_mode=SourceMode.WEBCAM, headless=False, max_frames=1)
    source = MagicMock()
    source.is_opened.return_value = True

    packet = MagicMock()
    packet.frame = MagicMock()
    source.read.return_value = packet

    pipeline_instance = MagicMock()
    mock_wait = MagicMock(return_value=-1)
    renderer = MagicMock()

    from app import InferenceOutput
    mock_out = MagicMock(spec=InferenceOutput)
    mock_out.detections = []
    mock_out.decision = MagicMock()
    mock_out.explanation = MagicMock()
    mock_out.runtime_metrics = MagicMock()

    class TestQueue(queue.Queue):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._returned = False

        def get_nowait(self):
            if getattr(self, "maxsize", 0) == 1:
                if not self._returned:
                    self._returned = True
                    return mock_out
                raise queue.Empty()
            return super().get_nowait()

    with patch('app.VisionPipeline'), \
         patch('app.ReplayRecorder'), \
         patch('cv2.imshow'), \
         patch('cv2.waitKey', mock_wait), \
         patch('cv2.destroyAllWindows'), \
         patch('app._finalize_run', return_value=0), \
         patch('queue.Queue', TestQueue):

        assert _run_streaming_mode(config, None, source, renderer, MagicMock()) == 0
        renderer.render.assert_called_once()
def test_streaming_mode_source_fail():
    config = VisionOSConfig(source_mode=SourceMode.WEBCAM, input_path="test.mp4", camera_index=0)
    source = MagicMock()
    source.is_opened.return_value = False
    logger = MagicMock()

    with patch("sys.stderr", MagicMock()):
        assert _run_streaming_mode(config, None, source, None, logger) == 1
    logger.log.assert_called_with("source_open_failed", mode=config.source_mode.value, input_path=config.input_path, camera=config.camera_index)

from app import _finalize_run
from runtime.benchmark import BenchmarkTracker

def test_finalize_run():
    config = VisionOSConfig(source_mode=SourceMode.VIDEO, record_path="out.jsonl", benchmark_output_path="bench.json")
    logger = MagicMock()
    tracker = MagicMock(spec=BenchmarkTracker)
    summary_mock = MagicMock()
    summary_mock.frames_processed = 10
    summary_mock.fps = 30.0
    summary_mock.average_inference_ms = 10.0
    summary_mock.dropped_frames = 0
    summary_mock.decision_switch_rate = 0.1
    summary_mock.scene_stability_score = 0.9
    summary_mock.to_dict.return_value = {}
    tracker.summary.return_value = summary_mock

    with patch("builtins.print") as mock_print:
        res = _finalize_run(config, tracker, logger)
        assert res == 0
        tracker.write_summary.assert_called_with("bench.json")
        assert logger.log.call_count == 3
        mock_print.assert_called_once()
