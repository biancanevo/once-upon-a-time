"""
Configuration module for the AI-powered Storyteller.

Provides environment-specific configuration classes and loading from .env files.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


def _find_and_load_dotenv():
    """
    Find and load .env file from multiple possible locations.

    Search order:
    1. Current working directory
    2. ~/.config/raspi-storyteller/.env
    3. ~/.raspi-storyteller.env
    4. Project directory (where this file is located)
    """
    possible_paths = [
        Path.cwd() / ".env",  # Current directory
        Path.home() / ".config" / "raspi-storyteller" / ".env",  # XDG config
        Path.home() / ".raspi-storyteller.env",  # Home directory
        Path(__file__).parent.parent.parent / ".env",  # Project root
    ]

    for env_path in possible_paths:
        if env_path.exists():
            load_dotenv(env_path)
            print(f"📁 Loaded config from: {env_path}")
            return str(env_path)

    # No .env found, use defaults
    load_dotenv()  # Still call to load any system env vars
    return None


# Load environment variables from .env file
_loaded_env_path = _find_and_load_dotenv()


class Config:
    """Base configuration class with common settings."""

    # Flask settings
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    DEBUG = os.getenv("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")
    PORT = int(os.getenv("FLASK_PORT", "5000"))

    # Ollama settings
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))

    # TTS settings
    TTS_PROVIDER = os.getenv("TTS_PROVIDER", "pyttsx3")
    EDGE_TTS_VOICE = os.getenv("EDGE_TTS_VOICE", "es-ES-PabloNeural")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")

    # Audio settings
    AUDIO_CACHE_DIR = Path(os.getenv("AUDIO_CACHE_DIR", "./audio_cache"))
    MAX_CACHE_SIZE_MB = int(os.getenv("MAX_CACHE_SIZE_MB", "500"))

    # Speech recognition settings
    SPEECH_LANGUAGE = os.getenv("SPEECH_LANGUAGE", "es-ES")
    SPEECH_TIMEOUT = int(os.getenv("SPEECH_TIMEOUT", "5"))

    # Hardware settings
    MOCK_HARDWARE = os.getenv("MOCK_HARDWARE", "True").lower() in ("true", "1", "yes")
    MOCK_OLLAMA = os.getenv("MOCK_OLLAMA", "False").lower() in ("true", "1", "yes")

    # LED settings
    LED_COUNT = int(os.getenv("LED_COUNT", "12"))
    LED_PIN = int(os.getenv("LED_PIN", "18"))
    LED_BRIGHTNESS = float(os.getenv("LED_BRIGHTNESS", "0.5"))

    # RFID settings
    RFID_DEBOUNCE_TIME = float(os.getenv("RFID_DEBOUNCE_TIME", "1.5"))

    # Slider settings (potentiometer via MCP3008 ADC)
    SLIDER_ADC_CHANNEL = int(os.getenv("SLIDER_ADC_CHANNEL", "0"))
    SLIDER_SPI_BUS = int(os.getenv("SLIDER_SPI_BUS", "0"))
    SLIDER_SPI_DEVICE = int(os.getenv("SLIDER_SPI_DEVICE", "1"))  # CE1 to avoid RFID conflict
    DEFAULT_STORY_LENGTH = int(os.getenv("DEFAULT_STORY_LENGTH", "5"))  # minutes

    # Logging settings
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
    LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")

    @classmethod
    def init_app(cls, app):
        """Initialize Flask app with this configuration."""
        # Ensure required directories exist
        cls.AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        Path(cls.LOG_FILE).parent.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(Config):
    """Development-specific configuration."""

    DEBUG = True
    MOCK_HARDWARE = True
    # TTS_PROVIDER inherited from Config (respects .env)


class ProductionConfig(Config):
    """Production configuration for Raspberry Pi deployment."""

    DEBUG = False
    MOCK_HARDWARE = False
    # TTS_PROVIDER inherited from Config (respects .env)


class TestingConfig(Config):
    """Testing configuration with all mocks enabled."""

    TESTING = True
    DEBUG = True
    MOCK_HARDWARE = True
    MOCK_OLLAMA = True
    # TTS_PROVIDER inherited from Config (respects .env)
    AUDIO_CACHE_DIR = Path("./test_audio_cache")
    LOG_LEVEL = "WARNING"


# Configuration mapping
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config():
    """Get configuration based on FLASK_ENV environment variable."""
    env = os.getenv("FLASK_ENV", "development")
    return config_by_name.get(env, DevelopmentConfig)
