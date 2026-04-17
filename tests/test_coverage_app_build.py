from app import _build_source
from common.config import VisionOSConfig
from common.models import SourceMode
from runtime.io import WebcamFrameSource, ReplayFrameSource, VideoFrameSource
from unittest.mock import patch, MagicMock, mock_open

@patch('cv2.VideoCapture')
def test_build_source_webcam(mock_vc):
    mock_vc.return_value = MagicMock()
    config = VisionOSConfig(source_mode=SourceMode.WEBCAM, camera_index=0)
    source = _build_source(config)
    assert isinstance(source, WebcamFrameSource)

@patch('builtins.open', new_callable=mock_open)
def test_build_source_replay(mock_file):
    config = VisionOSConfig(source_mode=SourceMode.REPLAY, input_path="fake.jsonl")
    with patch("pathlib.Path.open", mock_file):
        source = _build_source(config)
        assert isinstance(source, ReplayFrameSource)

@patch('cv2.VideoCapture')
def test_build_source_video(mock_vc):
    mock_vc.return_value = MagicMock()
    config = VisionOSConfig(source_mode=SourceMode.VIDEO, input_path="fake.mp4")
    with patch('pathlib.Path.is_file', return_value=True):
        source = _build_source(config)
        assert isinstance(source, VideoFrameSource)
