from unittest.mock import patch, MagicMock

import pytest

from app import _validate_input_path, main, parse_args
from common.config import VisionOSConfig
from common.models import SourceMode

def test_validate_input_path_webcam():
    config = VisionOSConfig(source_mode=SourceMode.WEBCAM)
    _validate_input_path(config)

def test_validate_input_path_missing():
    config = VisionOSConfig(source_mode=SourceMode.VIDEO, input_path="missing.mp4")
    with patch('pathlib.Path.is_file', return_value=False), \
         pytest.raises(FileNotFoundError, match="Video input not found: missing.mp4"):
        _validate_input_path(config)

def test_validate_input_path_replay_missing():
    config = VisionOSConfig(source_mode=SourceMode.REPLAY, input_path="missing.jsonl")
    with patch('pathlib.Path.is_file', return_value=False), \
         pytest.raises(FileNotFoundError, match="Replay input not found: missing.jsonl"):
        _validate_input_path(config)

@patch('app.parse_args')
@patch('sys.stderr')
def test_main_cli_error(mock_stderr, mock_parse):
    mock_parse.side_effect = ValueError("CLI error")
    assert main() == 1

@patch('app.parse_args')
def test_main_sequential_route(mock_parse):
    config = VisionOSConfig(source_mode=SourceMode.VIDEO, input_path="test.mp4")
    mock_parse.return_value = config

    with patch('app._validate_input_path'), \
         patch('app.load_policy') as mock_policy, \
         patch('app.VisionLogger'), \
         patch('app.FrameRenderer'), \
         patch('app._build_source'), \
         patch('app._log_run_started'), \
         patch('app._run_sequential_mode', return_value=0) as mock_seq:

         mock_policy.return_value = MagicMock(name="policy")
         assert main() == 0
         mock_seq.assert_called_once()

def test_parse_args_valid():
    with patch('sys.argv', ['app.py', '--source', 'video', '--input', 'foo.mp4']):
        config = parse_args()
        assert config.source_mode.value == "video"
        assert config.input_path == "foo.mp4"

def test_parse_args_missing_input():
    with patch('sys.argv', ['app.py', '--source', 'video']), \
         patch('sys.stderr', MagicMock()), \
         pytest.raises(SystemExit):
        parse_args()
