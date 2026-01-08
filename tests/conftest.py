"""
Pytest fixtures and configuration for the test suite.
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set testing environment
os.environ["FLASK_ENV"] = "testing"
os.environ["MOCK_HARDWARE"] = "True"
os.environ["MOCK_OLLAMA"] = "True"


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_cache_dir(temp_dir):
    """Create a temporary audio cache directory."""
    cache_dir = Path(temp_dir) / "audio_cache"
    cache_dir.mkdir()
    return str(cache_dir)


@pytest.fixture
def temp_cards_db(temp_dir):
    """Create a temporary cards database path."""
    return str(Path(temp_dir) / "cards_db.json")


@pytest.fixture
def mock_ollama():
    """Mock Ollama client for testing."""
    with patch("raspi_storyteller.services.story_generator.ollama") as mock:
        mock_client = MagicMock()
        mock_client.generate.return_value = {
            "response": "Once upon a time, there was a cat and a dog who were best friends."
        }
        mock.Client.return_value = mock_client
        yield mock


@pytest.fixture
def mock_edge_tts():
    """Mock edge_tts for testing."""
    with patch("raspi_storyteller.services.tts_engine.edge_tts") as mock:
        mock_communicate = MagicMock()
        mock_communicate.save = MagicMock()
        mock.Communicate.return_value = mock_communicate
        yield mock


@pytest.fixture
def mock_pyttsx3():
    """Mock pyttsx3 for testing."""
    with patch("raspi_storyteller.services.tts_engine.pyttsx3") as mock:
        mock_engine = MagicMock()
        mock.init.return_value = mock_engine
        yield mock


@pytest.fixture
def mock_pygame():
    """Mock pygame for audio testing."""
    with patch("raspi_storyteller.services.audio_manager.pygame") as mock:
        mock.mixer.music.get_busy.return_value = False
        yield mock


@pytest.fixture
def mock_speech_recognition():
    """Mock speech_recognition for testing."""
    with patch("raspi_storyteller.services.speech_recognizer.speech_recognition") as mock:
        mock_recognizer = MagicMock()
        mock_recognizer.recognize_google.return_value = "Tell me a story about a cat"
        mock.Recognizer.return_value = mock_recognizer
        yield mock


@pytest.fixture
def state(temp_cards_db):
    """Create a StorytellerState instance for testing."""
    from raspi_storyteller.state import StorytellerState
    return StorytellerState(cards_db_path=temp_cards_db)


@pytest.fixture
def tts_engine(temp_cache_dir):
    """Create a TTSEngine instance with mock provider."""
    from raspi_storyteller.services.tts_engine import TTSEngine
    return TTSEngine(
        provider="mock",
        cache_dir=temp_cache_dir,
        enable_fallback=False,
    )


@pytest.fixture
def audio_manager():
    """Create an AudioManager instance in mock mode."""
    from raspi_storyteller.services.audio_manager import AudioManager
    return AudioManager(mock=True)


@pytest.fixture
def speech_recognizer():
    """Create a SpeechRecognizer instance in mock mode."""
    from raspi_storyteller.services.speech_recognizer import SpeechRecognizer
    return SpeechRecognizer(mock=True)


@pytest.fixture
def story_generator():
    """Create a StoryGenerator instance in mock mode."""
    from raspi_storyteller.services.story_generator import StoryGenerator
    return StoryGenerator(mock=True)


@pytest.fixture
def mock_rfid_handler():
    """Create a mock RFID handler."""
    from raspi_storyteller.hardware.rfid_handler import MockRFIDHandler
    return MockRFIDHandler()


@pytest.fixture
def mock_led_controller():
    """Create a mock LED controller."""
    from raspi_storyteller.hardware.led_controller import MockLEDController
    return MockLEDController(led_count=12)


@pytest.fixture
def app():
    """Create a Flask test application."""
    from raspi_storyteller.app import create_app
    from raspi_storyteller.config import TestingConfig

    app = create_app(TestingConfig)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create a Flask test client."""
    return app.test_client()


@pytest.fixture
def app_context(app):
    """Create an application context."""
    with app.app_context():
        yield app
